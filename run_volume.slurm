#!/bin/bash
#
# OCR one Tropical Agriculturist volume (or issue) with Chandra 2 via vLLM.
#
# Array task N takes line N of $TASKLIST (tab-separated: tag, pdf path).
# Adapted from the sessional_papers runner, with two deliberate differences:
#
#   * It asks for a 3g.40gb MIG slice, not a whole H100. Chandra 2 is a ~8B
#     VLM: bf16 weights plus a working KV cache sit inside 40 GB comfortably,
#     and slices queue far sooner and let more volumes run at once than whole
#     cards do.
#   * --max-num-seqs is halved to 32 to match the smaller KV cache. On a full
#     80 GB card 64 concurrent sequences are fine; on a 40 GB slice they make
#     vLLM either preempt constantly or refuse to start.
#
# Resource flags (account, gpus, time, array) come from 05_submit.sh.
# Expects (via --export): TASKLIST, OUTDIR, BASE
#
#SBATCH --cpus-per-task=6
#SBATCH --mem=48G

set -uo pipefail

CHANDRA2="${CHANDRA2:-/project/def-jic823/chandra2}"
VENV="${VENV:-$CHANDRA2/venv}"

export HF_HOME="${HF_HOME:-/scratch/$USER/hf_cache}"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
# /home is only 50GB on Nibi; keep every JIT/compile cache off it.
export XDG_CACHE_HOME="/scratch/$USER/.cache"
export VLLM_CACHE_ROOT="$XDG_CACHE_HOME/vllm"
export FLASHINFER_WORKSPACE_BASE="$XDG_CACHE_HOME/flashinfer"
mkdir -p "$XDG_CACHE_HOME" "$VLLM_CACHE_ROOT" "$FLASHINFER_WORKSPACE_BASE"

module load python/3.11 gcc opencv/4.13.0 cuda/12.9
source "$VENV/bin/activate"

TASK_ID="${SLURM_ARRAY_TASK_ID:-1}"
LINE=$(sed -n "${TASK_ID}p" "$TASKLIST")
[ -n "$LINE" ] || { echo "[job] no task at line $TASK_ID of $TASKLIST"; exit 1; }
TAG=$(cut -f1 <<<"$LINE")
PDF=$(cut -f2 <<<"$LINE")
DEST="$OUTDIR/$TAG"

echo "=== tropical agriculturist: $TAG ==="
echo "[job] node=$(hostname) array_task=$TASK_ID"
echo "[job] pdf=$PDF"
echo "[job] out=$DEST"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

# Idempotent: a completed volume is left alone, so resubmitting is safe.
if find "$DEST" -name '*.md' -size +1k -print -quit 2>/dev/null | grep -q .; then
    echo "[job] already complete, skipping"
    exit 0
fi
[ -f "$PDF" ] || { echo "[job] MISSING PDF: $PDF"; exit 1; }
mkdir -p "$DEST"

SLOG="$BASE/logs/vllm-${SLURM_ARRAY_JOB_ID:-$SLURM_JOB_ID}_${TASK_ID}.log"
PORT=$(python -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')

# NOTE: do NOT export VLLM_API_KEY here. It is a *server* variable: if vLLM
# sees it at startup it enables API-key auth, /v1/models then answers 401, and
# the readiness probe below treats that as not-ready and spins until the job
# dies -- while the server is in fact healthy.

echo "[job] starting vLLM on port $PORT -> $SLOG"
vllm serve datalab-to/chandra-ocr-2 \
  --host 127.0.0.1 --port "$PORT" \
  --served-model-name chandra \
  --dtype bfloat16 \
  --max-model-len 18000 \
  --max-num-seqs 32 \
  --max-num-batched-tokens 8192 \
  --gpu-memory-utilization 0.85 \
  --enable-prefix-caching \
  --trust-remote-code \
  --mm-processor-kwargs '{"min_pixels":3136,"max_pixels":6291456}' \
  > "$SLOG" 2>&1 &
VLLM_PID=$!

cleanup() {
    kill "$VLLM_PID" 2>/dev/null || true
    wait "$VLLM_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# 360 x 10s = 60 min. Deliberately generous: under Lustre contention a load
# that normally takes ~6 min has been seen to take 20-40. Giving up early
# wastes the whole allocation and looks like a crash.
READY=0
for i in $(seq 1 360); do
    code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PORT}/v1/models" 2>/dev/null || echo 000)
    if [ "$code" = "200" ]; then
        READY=1; echo "[job] server ready after $((i*10))s"; break
    fi
    if [ "$code" = "401" ] || [ "$code" = "403" ]; then
        echo "[job] server is UP but returned HTTP $code -- an API key is set on"
        echo "      the server (VLLM_API_KEY in its environment). Unset it."
        exit 1
    fi
    if ! kill -0 "$VLLM_PID" 2>/dev/null; then
        echo "[job] SERVER DIED during startup"; tail -60 "$SLOG"; exit 1
    fi
    sleep 10
done
[ "$READY" -eq 1 ] || { echo "[job] server not ready within 60 min"; tail -60 "$SLOG"; exit 1; }

export VLLM_API_BASE="http://127.0.0.1:${PORT}/v1"
export VLLM_MODEL_NAME=chandra

echo "[job] running chandra at $(date -Is)"
chandra "$PDF" "$DEST" --method vllm
RC=$?

if [ $RC -eq 0 ] && find "$DEST" -name '*.md' -size +1k -print -quit 2>/dev/null | grep -q .; then
    echo "[job] OK $TAG at $(date -Is)"
    du -sh "$DEST"
else
    echo "[job] FAILED $TAG rc=$RC (no usable markdown written)"
    RC=${RC:-1}; [ $RC -eq 0 ] && RC=1
fi
exit $RC
