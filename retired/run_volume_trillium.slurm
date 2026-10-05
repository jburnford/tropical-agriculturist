#!/bin/bash
#
# OCR one Tropical Agriculturist volume with Chandra 2 on Trillium's GPU cluster.
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
# Array task N takes line N of $TASKLIST (tab-separated: tag, pdf path).
# Expects (via --export): TASKLIST, OUTDIR, BASE
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
# Chandra drops every block its layout model labels Page-Header or
# Page-Footer unless --include-headers-footers is passed (output.py
# parse_html defaults include_headers_footers=False). In this journal the
# article title sits at the head of the page and the folio at the foot, so
# the default silently discarded ~38% of article titles and every page
# number. --paginate_output adds the page boundaries needed for provenance.
CHANDRA_EXTRA="${CHANDRA_EXTRA:---include-headers-footers --paginate_output}"

module load apptainer cuda/12.6 2>/dev/null

TASK_ID="${SLURM_ARRAY_TASK_ID:-1}"
LINE=$(sed -n "${TASK_ID}p" "$TASKLIST")
[ -n "$LINE" ] || { echo "[job] no task at line $TASK_ID of $TASKLIST"; exit 1; }
TAG=$(cut -f1 <<<"$LINE")
PDF=$(cut -f2 <<<"$LINE")
DEST="$OUTDIR/$TAG"

echo "=== tropical agriculturist (trillium): $TAG ==="
echo "[job] node=$(hostname) array_task=$TASK_ID"
echo "[job] pdf=$PDF"
echo "[job] out=$DEST"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null

# Idempotent: a completed volume is left alone, so resubmitting is safe.
if find "$DEST" -name '*.md' -size +1k -print -quit 2>/dev/null | grep -q .; then
    echo "[job] already complete, skipping"; exit 0
fi
[ -f "$PDF" ] || { echo "[job] MISSING PDF: $PDF"; exit 1; }
mkdir -p "$DEST" "$SCR/tmp"/{,home,triton,inductor,xdg}
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
        --max-model-len 18000 \
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

echo "[job] running chandra at $(date -Is)"
chandra "$PDF" "$DEST" --method vllm --max-workers "$MAX_WORKERS" --batch-size "$BATCH_SIZE" \
        $CHANDRA_EXTRA
RC=$?

if [ $RC -eq 0 ] && find "$DEST" -name '*.md' -size +1k -print -quit 2>/dev/null | grep -q .; then
    echo "[job] OK $TAG at $(date -Is)"; du -sh "$DEST"
else
    echo "[job] FAILED $TAG rc=$RC (no usable markdown written)"
    RC=${RC:-1}; [ $RC -eq 0 ] && RC=1
fi
exit $RC
