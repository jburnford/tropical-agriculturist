#!/bin/bash
#
# OCR one *chunk* of Tropical Agriculturist documents with Chandra 2 on
# Trillium's GPU cluster. A chunk is a page-budgeted group built by
# make_chunks.py; every document in it shares one vLLM server.
#
# Derived from run_volume_plato.slurm. Trillium differs in four ways that matter:
#
#   * A whole H100 80GB, not a MIG slice. Chandra 2 is 9.9 GB of bf16 weights,
#     so at 0.90 utilisation this leaves ~62 GB of KV cache against the 27 GB a
#     3g.40gb slice had. MAX_NUM_SEQS and MAX_WORKERS are raised to match --
#     on Plato the binding constraint was client concurrency, not the GPU.
#   * Billing is GRES/gpu=1.0,CPU=0,Mem=0, so the 24 cores and 192 GB that come
#     with a quarter node are free. Asking for less buys nothing.
#   * $PROJECT resolves to a placeholder path here, which is misleading: the
#     allocation does exist at /project/def-jic823 (1 TB). The PDFs live there
#     because that is where Globus lands them; output goes to /scratch, which
#     has 25 TB against project's 1 TB.
#   * GPU nodes are reached through their own login node (trig-login01) and
#     their own Slurm cluster; the CPU login has no GPUs at all.
#
# This is the ONLY OCR script. run_volume_trillium.slurm is retired: two
# scripts drifted apart once, and a corpus ran without the flags as a result.
# Single-document and page-slice tests go through here too, via a small chunk.
#
# Array task N reads $CHUNKDIR/chunk_NNN.tsv (tab-separated: tag, pdf, pages,
# optional 0-based --page-range; when a range is given, pages must equal its
# size) and processes every document in it against a single vLLM server. Starting a
# server costs ~2.6 min against 1.8 min of OCR for a typical 72-page monthly
# issue, so one-document-per-job spent 29% of the allocation on startup.
#
# Each document is written as it completes, so a walltime overrun costs only
# the document in flight -- not the whole job, which is what made every Plato
# timeout produce nothing at all.
#
# Expects (via --export): CHUNKDIR, OUTDIR, BASE
#
# SciNet's submit filter is strict about how a GPU is requested: --gres and
# --gpus are both rejected outright, and **any** --mem is rejected too (memory
# is fixed at 192 GB per GPU by DefMemPerNode). Only --gpus-per-node passes.
#SBATCH --cpus-per-task=24
#SBATCH --gpus-per-node=h100:1

set -uo pipefail

SCR="${SCR:-/scratch/$USER}"
SIF="${SIF:-$SCR/containers/vllm-openai-v0.17.0.sif}"
MODEL_CACHE="${MODEL_CACHE:-$SCR/hf_cache}"
MODEL="${MODEL:-datalab-to/chandra-ocr-2}"
VENV="${VENV:-$SCR/chandra/venv}"

# Full H100 80GB (~72 GB usable at 0.90): measured on Plato's 3g.40gb slice
# (37 GB usable) MAX_NUM_SEQS=16 MAX_WORKERS=4 gave 4.7 pages/min. These are a
# starting point for the calibration volume, not a measured optimum.
MAX_NUM_SEQS="${MAX_NUM_SEQS:-48}"
MAX_WORKERS="${MAX_WORKERS:-16}"
BATCH_SIZE="${BATCH_SIZE:-64}"
# Chandra silently drops every block its layout model labels Page-Header or
# Page-Footer: output.py parse_html() defaults include_headers_footers=False.
# In this journal the article TITLE sits at the head of the page and the
# FOLIO at the foot, so the default cost us both -- titles survived only as
# buried prose and page numbers not at all. --paginate_output adds the page
# boundaries nothing else in the output preserves.
#
# Chandra also caps each page at 12,384 output tokens (settings.py). Pages
# that reach a cap are repetition loops, not long pages: in the Stage 1 test
# (job 1004419) no real page needed more than 12,085 tokens, while two loops
# ran to whatever cap was set (24,000 then). 16,000 leaves headroom for the
# header text without letting a loop cost double. vLLM's --max-model-len must
# cover image prompt + output (the model itself allows 262k).
#
# These are deliberately NOT overridable from the environment. The run that
# lost them was a default nobody looked at; nothing here should be one.
MAX_OUT=16000
MAX_MODEL_LEN=40000
CHANDRA_FLAGS=(--include-headers-footers --paginate_output --max-output-tokens "$MAX_OUT")
CONFIG="chandra ${CHANDRA_FLAGS[*]} | vllm --max-model-len $MAX_MODEL_LEN"
# submit_v4.sh writes $OUTDIR/RUN_CONFIG from this, before any task starts.
[ "${PRINT_CONFIG:-0}" = 1 ] && { echo "$CONFIG"; exit 0; }

module load apptainer cuda/12.6 2>/dev/null

TASK_ID="${SLURM_ARRAY_TASK_ID:-1}"
CHUNK="$CHUNKDIR/chunk_$(printf '%03d' "$TASK_ID").tsv"
[ -f "$CHUNK" ] || { echo "[job] no chunk file at $CHUNK"; exit 1; }
CHECK="$BASE/check_doc.py"
[ -f "$CHECK" ] || { echo "[job] no validator at $CHECK"; exit 1; }

# Never write into a tree made under other settings. The skip-if-complete rule
# below would otherwise report an old run's output as "already complete" --
# a success message from a check that cannot see what it is checking.
case "$(basename "$OUTDIR")" in
    output|output_v2|output_v3|output_hdr)
        echo "[job] REFUSING: $OUTDIR is a pre-2026-09-29 tree made with other flags"; exit 1 ;;
esac
# RUN_CONFIG is written once at submit time (never here: concurrent array
# tasks would race on creating it).
[ -f "$OUTDIR/RUN_CONFIG" ] || { echo "[job] REFUSING: no $OUTDIR/RUN_CONFIG (submit with submit_v4.sh)"; exit 1; }
[ "$(cat "$OUTDIR/RUN_CONFIG")" = "$CONFIG" ] || {
    echo "[job] REFUSING: $OUTDIR/RUN_CONFIG differs from this script:"
    echo "      tree:   $(cat "$OUTDIR/RUN_CONFIG")"; echo "      script: $CONFIG"; exit 1; }

NDOCS=$(wc -l < "$CHUNK")
NPAGES=$(awk -F'\t' '{s+=$3} END {print s+0}' "$CHUNK")
echo "=== tropical agriculturist (trillium): chunk $TASK_ID ==="
echo "[job] node=$(hostname) docs=$NDOCS pages=$NPAGES"
echo "[job] config: $CONFIG"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null

# A document counts as complete only if it passes the validator, not merely
# because a markdown file exists.
valid() { python3 "$CHECK" "$OUTDIR/$1" "$2" "$MAX_OUT"; }

# Idempotent at chunk level too: if every document is already written there is
# no reason to pay for a server at all.
REMAINING=0
while IFS=$'\t' read -r tag pdf pages range; do
    [ -n "$tag" ] || continue
    valid "$tag" "$pages" >/dev/null 2>&1 || REMAINING=$((REMAINING+1))
done < "$CHUNK"
if [ "$REMAINING" -eq 0 ]; then
    echo "[job] all $NDOCS documents already complete, nothing to do"; exit 0
fi
echo "[job] $REMAINING of $NDOCS document(s) outstanding"
mkdir -p "$SCR/tmp"/{,home,triton,flashinfer,inductor,xdg}
export APPTAINER_TMPDIR="$SCR/tmp"

# A free port, so two tasks on the same node cannot collide. Trillium packs up
# to four jobs per node (one per GPU), so this matters more here than on Plato.
PORT=$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')
SLOG="$BASE/logs/vllm-${SLURM_ARRAY_JOB_ID:-$SLURM_JOB_ID}_${TASK_ID}.log"

# Several libraries JIT-compile kernels at startup and cache them under $HOME,
# which is not writable from inside the container. Each failure surfaces as a
# different and misleading downstream error -- Triton's showed up as "Model
# architectures ['Qwen3_5ForConditionalGeneration'] failed to be inspected",
# FlashInfer's as "Engine core initialization failed".
#
# --home is the fix that covers all of them at once: it bind-mounts a scratch
# directory *as* $HOME, so anything calling Path.home() lands somewhere
# writable. A plain --env HOME=... does not work; Apptainer sets $HOME itself
# and overrides it. The per-library *_CACHE_DIR variables below are belt and
# braces for anything that reads them before resolving $HOME.
echo "[job] starting vLLM (apptainer) on port $PORT -> $SLOG"
apptainer exec --nv \
    --home "$SCR/tmp/home:/home/$USER" \
    --bind "$MODEL_CACHE:/root/.cache/huggingface" \
    --bind "$SCR:$SCR" \
    --bind "$BASE:$BASE" \
    --bind /etc/pki:/etc/pki \
    --bind /etc/ssl:/etc/ssl \
    --env HF_HOME=/root/.cache/huggingface \
    --env HF_HUB_OFFLINE=1 \
    --env TRITON_CACHE_DIR="$SCR/tmp/triton" \
    --env FLASHINFER_WORKSPACE_BASE="$SCR/tmp/flashinfer" \
    --env TORCHINDUCTOR_CACHE_DIR="$SCR/tmp/inductor" \
    --env XDG_CACHE_HOME="$SCR/tmp/xdg" \
    --env REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt \
    --env SSL_CERT_FILE=/etc/pki/tls/certs/ca-bundle.crt \
    --env HF_HUB_DISABLE_XET=1 \
    "$SIF" \
    vllm serve "$MODEL" \
        --host 127.0.0.1 --port "$PORT" \
        --served-model-name chandra \
        --dtype bfloat16 \
        --max-model-len "$MAX_MODEL_LEN" \
        --max-num-seqs "$MAX_NUM_SEQS" \
        --max_num_batched_tokens 16384 \
        --gpu-memory-utilization 0.90 \
        --enable-prefix-caching \
        --no-enforce-eager \
        --mm-processor-kwargs '{"min_pixels": 3136, "max_pixels": 6291456}' \
    > "$SLOG" 2>&1 &
VLLM_PID=$!

cleanup() { kill "$VLLM_PID" 2>/dev/null || true; wait "$VLLM_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

# 20 min, as on Plato. /scratch here is VAST rather than GPFS, so a cold start
# should be quicker, but the allowance costs nothing when the server is ready.
READY=0
for i in $(seq 1 120); do
    code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PORT}/v1/models" 2>/dev/null || echo 000)
    if [ "$code" = "200" ]; then READY=1; echo "[job] server ready after $((i*10))s"; break; fi
    if ! kill -0 "$VLLM_PID" 2>/dev/null; then
        echo "[job] SERVER DIED during startup"; tail -40 "$SLOG"; exit 1
    fi
    sleep 10
done
[ "$READY" -eq 1 ] || { echo "[job] server not ready in 20 min"; tail -40 "$SLOG"; exit 1; }

source "$VENV/bin/activate"
export VLLM_API_BASE="http://127.0.0.1:${PORT}/v1"
export VLLM_MODEL_NAME=chandra
export VLLM_API_KEY=EMPTY

FAILED=0; DONE=0; SKIPPED=0; ATTEMPTED=0
while IFS=$'\t' read -r TAG PDF PAGES RANGE; do
    [ -n "$TAG" ] || continue
    DEST="$OUTDIR/$TAG"

    if valid "$TAG" "$PAGES" >/dev/null 2>&1; then
        echo "[doc] SKIP $TAG (already complete and valid)"; SKIPPED=$((SKIPPED+1)); continue
    fi
    if [ ! -f "$PDF" ]; then
        echo "[doc] MISSING PDF: $PDF"; FAILED=$((FAILED+1)); continue
    fi
    # Partial or invalid output from an earlier attempt: set it aside, don't mix.
    [ -d "$DEST" ] && mkdir -p "$OUTDIR/_failed" && mv "$DEST" "$OUTDIR/_failed/${TAG}.$(date +%s)"

    CMD=(chandra "$PDF" "$DEST" --method vllm --max-workers "$MAX_WORKERS" --batch-size "$BATCH_SIZE"
         "${CHANDRA_FLAGS[@]}")
    [ -n "$RANGE" ] && CMD+=(--page-range "$RANGE")

    mkdir -p "$DEST"
    echo "[doc] START $TAG ($PAGES pp) at $(date -Is)"
    echo "[doc] cmd: ${CMD[*]}"
    t0=$(date +%s)
    "${CMD[@]}"
    rc=$?
    t1=$(date +%s)
    mins=$(awk "BEGIN{printf \"%.1f\", ($t1-$t0)/60}")
    ATTEMPTED=$((ATTEMPTED+1))

    RESULT=$(valid "$TAG" "$PAGES" 2>&1); vrc=$?
    echo "$RESULT" >> "$OUTDIR/_validation.tsv"
    if [ $rc -eq 0 ] && [ $vrc -eq 0 ]; then
        rate=$(awk "BEGIN{printf \"%.1f\", $PAGES/(($t1-$t0)/60)}")
        echo "[doc] OK $TAG in ${mins}min (${rate} pages/min) | $RESULT"
        DONE=$((DONE+1))
    else
        echo "[doc] FAILED $TAG rc=$rc after ${mins}min | $RESULT"
        FAILED=$((FAILED+1))
        mkdir -p "$OUTDIR/_failed" && mv "$DEST" "$OUTDIR/_failed/${TAG}.$(date +%s)"
        # If the very first document fails validation, the cause is almost
        # certainly configuration, and every later document would fail the
        # same way. Stop now: this costs one document, not a chunk.
        if [ "$ATTEMPTED" -eq 1 ]; then
            echo "[job] ABORT: first document failed validation -- not spending the rest of the chunk"
            exit 1
        fi
    fi
done < "$CHUNK"

echo "[job] chunk $TASK_ID finished at $(date -Is): $DONE ok, $SKIPPED skipped, $FAILED failed"
[ "$FAILED" -eq 0 ] || exit 1
exit 0
