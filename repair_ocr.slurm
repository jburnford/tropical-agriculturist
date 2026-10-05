#!/bin/bash
#
# Re-read selected pages (packed by build_repair_pdfs.py) with Chandra 2.
# Stage 4 repair: capped loops, hallucinations on faded/show-through pages.
#
# Array task N reads the Nth *.pdf (sorted) in $INDIR and writes Chandra's
# output to $OUTDIR/<stem>/. Nothing here touches output_v4: the decision
# to splice a re-read into the corpus is made afterwards, page by page, by
# repair_decide.py.
#
# vLLM startup and Chandra flags are copied from run_chunk_trillium.slurm
# (md5 f1060759) except MAX_OUT: 32,000 instead of 16,000, because capped
# pages include dense tables that were genuinely cut off, and a loop on a
# few hundred pages costs minutes, not hours. max-model-len 40,000 still
# covers the ~3k-token image prompt plus 32,000 output.
#
# Expects (via --export): INDIR, OUTDIR, BASE
#SBATCH --cpus-per-task=24
#SBATCH --gpus-per-node=h100:1

set -uo pipefail

SCR="${SCR:-/scratch/$USER}"
SIF="${SIF:-$SCR/containers/vllm-openai-v0.17.0.sif}"
MODEL_CACHE="${MODEL_CACHE:-$SCR/hf_cache}"
MODEL="${MODEL:-datalab-to/chandra-ocr-2}"
VENV="${VENV:-$SCR/chandra/venv}"
MAX_NUM_SEQS=48
MAX_WORKERS=16
BATCH_SIZE=64
MAX_OUT="${MAX_OUT:-32000}"   # repair default; faded-page re-reads use 16000 (loops there only stall batches)
MAX_MODEL_LEN=40000
CHANDRA_FLAGS=(--include-headers-footers --paginate_output --max-output-tokens "$MAX_OUT")

module load apptainer cuda/12.6 2>/dev/null

TASK_ID="${SLURM_ARRAY_TASK_ID:-1}"
mapfile -t PDFS < <(ls "$INDIR"/*.pdf | sort)
PDF="${PDFS[$((TASK_ID-1))]:-}"
[ -n "$PDF" ] || { echo "[job] no pdf #$TASK_ID in $INDIR"; exit 1; }
STEM=$(basename "$PDF" .pdf)
echo "=== stage4 repair: task $TASK_ID $PDF node=$(hostname)"
echo "[job] flags: ${CHANDRA_FLAGS[*]} | vllm --max-model-len $MAX_MODEL_LEN"
if [ -f "$OUTDIR/$STEM/$STEM.md" ]; then echo "[job] $STEM already done"; exit 0; fi

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

source "$VENV/bin/activate"
export VLLM_API_BASE="http://127.0.0.1:${PORT}/v1"
export VLLM_MODEL_NAME=chandra
export VLLM_API_KEY=EMPTY

mkdir -p "$OUTDIR"
t0=$(date +%s)
chandra "$PDF" "$OUTDIR" --method vllm --max-workers "$MAX_WORKERS" --batch-size "$BATCH_SIZE" "${CHANDRA_FLAGS[@]}"
rc=$?
t1=$(date +%s)
n=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['num_pages'])" "$OUTDIR/$STEM/${STEM}_metadata.json" 2>/dev/null || echo 0)
echo "[job] $STEM rc=$rc pages=$n in $(( (t1-t0)/60 ))min"
[ $rc -eq 0 ] && [ "$n" -eq "$(wc -l < "$INDIR/$STEM.index.tsv")" ] || { echo "[job] FAILED: page count mismatch or rc"; exit 1; }
