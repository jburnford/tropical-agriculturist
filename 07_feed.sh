#!/bin/bash
#
# Feed volumes to the OCR queue as their PDFs finish downloading.
#
# Rebuilds the manifest from whatever has landed in pdfs/, then calls
# 05_submit.sh, which already skips anything finished or already queued. So
# running this on a timer turns a slow download into a rolling queue instead of
# a wait-then-submit step.
#
# MAX_ACTIVE caps how many of our array jobs may be queued or running at once.
# On Plato this is deliberately 1: it is a small shared cluster with three MIG
# slices total, and submitting one array per walltime bucket would otherwise
# quietly occupy three of them.
#
# Usage:
#   BASE=/project/clifford/tropical ACCOUNT=hpc_p_clifford \
#     GPU_FLAG=--gres=gpu:3g.40gb:1 JOBPREFIX=tap MAX_ACTIVE=1 \
#     RUNNER=$BASE/run_volume_plato.slurm \
#     nohup bash 07_feed.sh > $BASE/logs/feed.log 2>&1 &
#
#   bash 07_feed.sh --once      # one pass, no loop
#
set -uo pipefail

BASE="${BASE:-/project/clifford/tropical}"
JOBPREFIX="${JOBPREFIX:-tap}"
PDFS="${PDFS:-$BASE/pdfs}"
# Per-feeder manifest, keyed by JOBPREFIX. Two feeders sharing one
# manifest.tsv silently overwrite each other -- the second rebuilds it for its
# own volume range, and the first then submits from a file describing somebody
# else's volumes.
MANIFEST="${MANIFEST:-$BASE/manifest.${JOBPREFIX:-tap}.tsv}"
VOLUMES="${VOLUMES:-1-101}"
INTERVAL="${INTERVAL:-600}"
MAX_ACTIVE="${MAX_ACTIVE:-1}"
RATE="${RATE:-}"            # pass through to 04_manifest.py once calibrated

ONCE=0
[ "${1:-}" = "--once" ] && ONCE=1

active_jobs() {
    command -v squeue >/dev/null 2>&1 || { echo 0; return; }
    squeue -u "$USER" -h -o '%j' -t PENDING,RUNNING,SUSPENDED 2>/dev/null \
        | grep -c "^${JOBPREFIX}-" || true
}

download_running() {
    # 03_download.py writes .pdf.part and renames on completion, so a partial
    # file is never visible as a .pdf. Matching on "[0]3_" keeps this pgrep
    # from matching its own command line.
    pgrep -f "[0]3_download.py" >/dev/null 2>&1
}

pass=0
while :; do
    pass=$((pass + 1))
    n_pdf=$(ls "$PDFS"/*.pdf 2>/dev/null | wc -l)
    n_act=$(active_jobs)
    printf '[%s] pass %d: %d pdfs, %d active %s job(s)\n' \
        "$(date -Is)" "$pass" "$n_pdf" "$n_act" "$JOBPREFIX"

    if [ "$n_act" -ge "$MAX_ACTIVE" ]; then
        echo "  at MAX_ACTIVE=$MAX_ACTIVE, not submitting this pass"
    elif [ "$n_pdf" -eq 0 ]; then
        echo "  no PDFs yet"
    else
        rate_arg=""
        [ -n "$RATE" ] && rate_arg="--rate $RATE"
        python3 "$BASE/04_manifest.py" --pdfs "$PDFS" --out "$MANIFEST" \
            --volumes "$VOLUMES" $rate_arg 2>&1 | sed 's/^/  /'
        MANIFEST="$MANIFEST" bash "$BASE/05_submit.sh" 2>&1 | sed 's/^/  /'
    fi

    if [ "$ONCE" -eq 1 ]; then
        break
    fi

    # Stop only when the download is finished *and* everything in the manifest
    # is either done or in the queue -- otherwise a lull in the download would
    # end the loop early.
    if ! download_running; then
        outstanding=$(MANIFEST="$MANIFEST" bash "$BASE/05_submit.sh" --dry-run 2>/dev/null \
            | grep -oE '[0-9]+ documents outstanding' | awk '{s+=$1} END {print s+0}')
        if [ "${outstanding:-0}" -eq 0 ] && [ "$(active_jobs)" -eq 0 ]; then
            echo "[$(date -Is)] download finished and nothing outstanding; feeder exiting"
            break
        fi
    fi
    sleep "$INTERVAL"
done
