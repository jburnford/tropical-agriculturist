#!/bin/bash
#
# Pull completed OCR output from the cluster to local storage.
#
# Only volumes that have actually finished are transferred: Chandra writes a
# document's Markdown once its last page completes, so a directory containing a
# non-empty .md is done, and one without is either still running or failed. The
# remote is the source of truth for that judgement, which is why the list is
# built there rather than inferred from what happens to be on disk locally.
#
# Incremental and safe to re-run: rsync skips unchanged files, so repeated runs
# cost a directory listing rather than a re-transfer.
#
# Usage:
#   bash 08_pull.sh                 # one pass
#   bash 08_pull.sh --loop          # keep pulling every $INTERVAL until stopped
#   bash 08_pull.sh --dry-run
#
set -uo pipefail

REMOTE="${REMOTE:-plato}"
REMOTE_OUT="${REMOTE_OUT:-/project/clifford/tropical/output}"
LOCAL_OUT="${LOCAL_OUT:-/home/jic823/tropical/output}"
INTERVAL="${INTERVAL:-900}"
LOG="${LOG:-/home/jic823/tropical/logs/pull.log}"

LOOP=0; DRY=""
while [ $# -gt 0 ]; do
    case "$1" in
        --loop)    LOOP=1 ;;
        --dry-run) DRY="--dry-run" ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
    shift
done

mkdir -p "$LOCAL_OUT" "$(dirname "$LOG")"

pull_once() {
    local list rc n
    list="$(mktemp)"
    # A volume counts as complete only if it holds a non-empty .md. Printing the
    # directory name (not the file) keeps sidecars -- HTML, metadata, extracted
    # images -- with their volume.
    if ! ssh -o BatchMode=yes "$REMOTE" \
        "cd '$REMOTE_OUT' 2>/dev/null && for d in */; do
             find \"\$d\" -name '*.md' -size +1k -print -quit 2>/dev/null | grep -q . && printf '%s\n' \"\${d%/}\"
         done" > "$list" 2>/dev/null
    then
        echo "[$(date -Is)] could not reach $REMOTE" | tee -a "$LOG"
        rm -f "$list"; return 1
    fi

    n=$(wc -l < "$list")
    if [ "$n" -eq 0 ]; then
        echo "[$(date -Is)] nothing complete yet" | tee -a "$LOG"
        rm -f "$list"; return 0
    fi

    echo "[$(date -Is)] $n completed volume(s) on $REMOTE" | tee -a "$LOG"
    # -r is explicit: --files-from implies --dirs, not --recursive, so without
    # it rsync creates each volume's directory and copies nothing inside.
    rsync -a -r --info=stats2 $DRY \
        --files-from="$list" \
        "$REMOTE:$REMOTE_OUT/" "$LOCAL_OUT/" 2>&1 | tail -12 | tee -a "$LOG"
    rc=$?
    rm -f "$list"

    local have
    have=$(find "$LOCAL_OUT" -name '*.md' -size +1k 2>/dev/null | wc -l)
    echo "[$(date -Is)] local now holds $have completed volume(s), $(du -sh "$LOCAL_OUT" 2>/dev/null | cut -f1)" \
        | tee -a "$LOG"
    return $rc
}

if [ "$LOOP" -eq 1 ]; then
    echo "[$(date -Is)] pull loop started (every ${INTERVAL}s)" | tee -a "$LOG"
    while :; do
        pull_once
        sleep "$INTERVAL"
    done
else
    pull_once
fi
