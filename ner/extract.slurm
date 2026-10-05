#!/bin/bash
# Open entity extraction over articles with Qwen3.8-27B-FP8 behind vLLM on one Trillium H100.
# Expects (via --export): IN (articles jsonl), OUT (mentions jsonl)
# SciNet rejects --gres/--gpus/--mem; only --gpus-per-node passes (see run_chunk_trillium.slurm).
#SBATCH --cpus-per-task=24
#SBATCH --gpus-per-node=h100:1
#SBATCH --job-name=ta-ner
#SBATCH --time=1:00:00
#SBATCH --output=/scratch/jic823/tropical/logs/%x-%j.out
set -uo pipefail
SCR=/scratch/jic823
BASE=$SCR/tropical
A=$BASE/articles
SIF=$SCR/containers/vllm-openai-v0.17.0.sif
MODEL=$SCR/hf_cache/hub/models--Qwen--Qwen3.8-27B-FP8/snapshots/017b9c7af6b5689d5dd426a76e0bc077eb5ca20a
MAX_MODEL_LEN=32768
module load apptainer cuda/12.6 2>/dev/null

echo "[job] node=$(hostname) job=$SLURM_JOB_ID in=${IN} out=${OUT} $(date -Is)"
echo "[job] md5 $(md5sum $BASE/ner/extract_entities.py | cut -c1-8) extract_entities.py; $(md5sum $IN | cut -c1-8) $(basename $IN)"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null
[ -d "$MODEL" ] || { echo "[job] no model at $MODEL"; exit 1; }

mkdir -p "$SCR/tmp"/{,home,triton,flashinfer,inductor,xdg}
export APPTAINER_TMPDIR="$SCR/tmp"
PORT=$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')
SLOG="$BASE/logs/vllm-label-$SLURM_JOB_ID.log"

# --home: libraries JIT-cache under $HOME, which is not writable in the container
# (Triton/FlashInfer fail with misleading errors otherwise; see run_chunk_trillium.slurm).
apptainer exec --nv \
    --home "$SCR/tmp/home:/home/$USER" \
    --bind "$SCR:$SCR" \
    --bind /etc/pki:/etc/pki \
    --bind /etc/ssl:/etc/ssl \
    --env HF_HUB_OFFLINE=1 \
    --env TRITON_CACHE_DIR="$SCR/tmp/triton" \
    --env FLASHINFER_WORKSPACE_BASE="$SCR/tmp/flashinfer" \
    --env TORCHINDUCTOR_CACHE_DIR="$SCR/tmp/inductor" \
    --env XDG_CACHE_HOME="$SCR/tmp/xdg" \
    "$SIF" \
    vllm serve "$MODEL" \
        --host 127.0.0.1 --port "$PORT" \
        --served-model-name qwen38 \
        --max-model-len "$MAX_MODEL_LEN" \
        --max-num-seqs 32 \
        --gpu-memory-utilization 0.90 \
        --enable-prefix-caching \
        --limit-mm-per-prompt '{"image":0,"video":0}' \
    > "$SLOG" 2>&1 &
VLLM_PID=$!
cleanup() { kill "$VLLM_PID" 2>/dev/null || true; wait "$VLLM_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

READY=0
for i in $(seq 1 120); do
    code=$(curl -s -m 5 -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PORT}/v1/models" 2>/dev/null || echo 000)
    if [ "$code" = "200" ]; then READY=1; echo "[job] server ready after $((i*10))s"; break; fi
    if ! kill -0 "$VLLM_PID" 2>/dev/null; then echo "[job] SERVER DIED during startup"; tail -40 "$SLOG"; exit 1; fi
    sleep 10
done
[ "$READY" -eq 1 ] || { echo "[job] server not ready in 20 min"; tail -40 "$SLOG"; exit 1; }

python3 "$BASE/ner/extract_entities.py" --base-url "http://127.0.0.1:${PORT}/v1" --model qwen38 \
    --in "$IN" --out "$OUT" --parallel 16
echo "[job] done $(date -Is) exit=$?"
