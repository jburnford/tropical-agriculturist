#!/bin/bash
#SBATCH --job-name=ta-classify
## no --partition: plato's submit filter rejects explicit partition names for
## this account and auto-routes by --gres (copied from canada50/plato_qwen38.slurm)
#SBATCH --gres=gpu:3g.40gb:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=08:00:00
#SBATCH --output=%x-%j.out
#
# Classify all 64,004 Tropical Agriculturist headings as
# ARTICLE / SUB / DEPT / FRONT with Qwen3.8-27B-FP8.
#
# Serving setup is lifted wholesale from canada50/cluster/plato_qwen38.slurm,
# which is known to work on this slice: FP8 weights are ~29 GB, so a 3g.40gb
# MIG slice fits them with enough left for a 40K context.
#
# Submit:  sbatch plato_classify.slurm
# Vars:    BATCH=20 PARALLEL=8 LIMIT_DOCS=3 sbatch plato_classify.slurm
#          HEADINGS=$TA/headings_val.jsonl LABELS=$TA/labels_val.jsonl sbatch ...

set -euo pipefail
C50=${C50:-$HOME/projects/canada50}
TA=${TA:-/project/clifford/tropical_parse}
MODEL_DIR=${MODEL_DIR:-$C50/models/Qwen3.8-27B-FP8}
SIF=${SIF:-$C50/containers/vllm.sif}
MODEL_NAME=${MODEL_NAME:-Qwen/Qwen3.8-27B-FP8}
MAXLEN=${MAXLEN:-40960}
PORT=${PORT:-8137}

echo "node $(hostname)  job $SLURM_JOB_ID  $(date -Is)"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || true

export HF_HUB_OFFLINE=1 HF_HOME=$C50/hf_cache VLLM_LOGGING_LEVEL=WARNING
module load apptainer/1.4.5 2>/dev/null || module load apptainer 2>/dev/null || true
CTR=$(command -v apptainer || command -v singularity)
export APPTAINERENV_HF_HUB_OFFLINE=1 APPTAINERENV_HF_HOME=$C50/hf_cache
RUN=("$CTR" exec --nv --bind "$C50":"$C50" --bind "$TA":"$TA" "$SIF" python3)
CLI=("$CTR" exec --bind "$TA":"$TA" "$SIF" python3)

"${RUN[@]}" -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_DIR" --served-model-name "$MODEL_NAME" \
    --port "$PORT" --host 127.0.0.1 \
    --max-model-len "$MAXLEN" --gpu-memory-utilization "${GPU_UTIL:-0.93}" \
    --max-num-seqs "${MAX_SEQS:-8}" \
    --limit-mm-per-prompt '{"image":0,"video":0}' \
    > "$TA/vllm-$SLURM_JOB_ID.log" 2>&1 &
VLLM_PID=$!
trap 'kill $VLLM_PID 2>/dev/null || true' EXIT INT TERM

for i in $(seq 1 180); do
    code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/v1/models" || echo 000)
    [ "$code" = "200" ] && { echo "server up after ${i}x5s"; break; }
    kill -0 $VLLM_PID 2>/dev/null || { echo "SERVER DIED"; tail -30 "$TA/vllm-$SLURM_JOB_ID.log"; exit 1; }
    sleep 5
done

"${CLI[@]}" "$TA/classify_headings.py" \
    --base-url "http://127.0.0.1:$PORT/v1" --model "$MODEL_NAME" \
    --headings "${HEADINGS:-$TA/headings.jsonl}" --out "${LABELS:-$TA/labels.jsonl}" \
    --batch "${BATCH:-20}" --parallel "${PARALLEL:-3}" \
    ${LIMIT_DOCS:+--limit-docs "$LIMIT_DOCS"}

echo "classification done $(date -Is)"
