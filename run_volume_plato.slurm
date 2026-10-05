#!/bin/bash
#
# OCR one Tropical Agriculturist volume with Chandra 2 on Plato.
#
# Plato differs from Nibi in three ways that matter, all reflected below and
# all taken from the working run_chandra_sp_rx.sh rather than guessed:
#
#   * vLLM runs inside an Apptainer container, not a venv. The chandra *client*
#     still comes from the venv at ~/chandra_plato/venv.
#   * GPUs are requested with --gres=gpu:3g.40gb:1, and **--partition must not
#     be passed** -- Plato routes GPU jobs by type and rejects explicit
#     partition requests with "not allowed to submit".
#   * The node has 16 CPUs against 3 MIG slices, so a job asking for 8 CPUs
#     already takes half the node. We deliberately run one slice at a time
#     (this is a small shared cluster), so 8 is fine.
#
# Array task N takes line N of $TASKLIST (tab-separated: tag, pdf path).
# Expects (via --export): TASKLIST, OUTDIR, BASE
#
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G

set -uo pipefail

SIF="${SIF:-$HOME/projects/def-jic823/containers/vllm-openai-v0.17.0.sif}"
MODEL_CACHE="${MODEL_CACHE:-$HOME/projects/def-jic823/models}"
MODEL="${MODEL:-datalab-to/chandra-ocr-2}"
VENV="${VENV:-$HOME/chandra_plato/venv}"

# Tunables, so the same runner serves both slice sizes on platogpu003.
#   3g.40gb (~37 GB usable): MAX_NUM_SEQS=16 MAX_WORKERS=4   -- measured 4.7 pages/min
#   2g.20gb (~18 GB usable): MAX_NUM_SEQS=6  MAX_WORKERS=2
# Chandra 2 is 9.9 GB of bf16 weights, so a 20 GB slice leaves only ~8 GB of KV
# cache; 16 concurrent sequences do not fit and vLLM either thrashes or refuses
# to start. Fewer client workers to match, and because the node has 16 CPUs for
# three slices.
MAX_NUM_SEQS="${MAX_NUM_SEQS:-16}"
MAX_WORKERS="${MAX_WORKERS:-4}"
BATCH_SIZE="${BATCH_SIZE:-28}"

module load apptainer cuda/12.6

TASK_ID="${SLURM_ARRAY_TASK_ID:-1}"
LINE=$(sed -n "${TASK_ID}p" "$TASKLIST")
[ -n "$LINE" ] || { echo "[job] no task at line $TASK_ID of $TASKLIST"; exit 1; }
TAG=$(cut -f1 <<<"$LINE")
PDF=$(cut -f2 <<<"$LINE")
DEST="$OUTDIR/$TAG"

echo "=== tropical agriculturist (plato): $TAG ==="
echo "[job] node=$(hostname) array_task=$TASK_ID"
echo "[job] pdf=$PDF"
echo "[job] out=$DEST"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null

# Idempotent: a completed volume is left alone, so resubmitting is safe.
if find "$DEST" -name '*.md' -size +1k -print -quit 2>/dev/null | grep -q .; then
    echo "[job] already complete, skipping"; exit 0
fi
[ -f "$PDF" ] || { echo "[job] MISSING PDF: $PDF"; exit 1; }
mkdir -p "$DEST" "$HOME/.apptainer/tmp"
export APPTAINER_TMPDIR="$HOME/.apptainer/tmp"

# A free port, so two tasks on the same node cannot collide.
PORT=$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')
SLOG="$BASE/logs/vllm-${SLURM_ARRAY_JOB_ID:-$SLURM_JOB_ID}_${TASK_ID}.log"

echo "[job] starting vLLM (apptainer) on port $PORT -> $SLOG"
apptainer exec --nv \
    --bind "$MODEL_CACHE:/root/.cache/huggingface" \
    --bind "$HOME:$HOME" \
    --bind "$BASE:$BASE" \
    --bind /etc/pki:/etc/pki \
    --bind /etc/ssl:/etc/ssl \
    --env HF_HOME=/root/.cache/huggingface \
    --env HF_HUB_OFFLINE=1 \
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
        --max_num_batched_tokens 8192 \
        --gpu-memory-utilization 0.90 \
        --enable-prefix-caching \
        --no-enforce-eager \
        --mm-processor-kwargs '{"min_pixels": 3136, "max_pixels": 6291456}' \
    > "$SLOG" 2>&1 &
VLLM_PID=$!

cleanup() { kill "$VLLM_PID" 2>/dev/null || true; wait "$VLLM_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

# 20 min. Generous next to the 10 the sp_rx script allowed, because the model
# is pulled off GPFS and a cold cache is markedly slower than a warm one.
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
chandra "$PDF" "$DEST" --method vllm --max-workers "$MAX_WORKERS" --batch-size "$BATCH_SIZE"
RC=$?

if [ $RC -eq 0 ] && find "$DEST" -name '*.md' -size +1k -print -quit 2>/dev/null | grep -q .; then
    echo "[job] OK $TAG at $(date -Is)"; du -sh "$DEST"
else
    echo "[job] FAILED $TAG rc=$RC (no usable markdown written)"
    RC=${RC:-1}; [ $RC -eq 0 ] && RC=1
fi
exit $RC
