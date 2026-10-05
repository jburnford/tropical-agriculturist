#!/bin/bash
#
# Submit one stage of the header/footer re-run (see RERUN_PLAN.md).
#
#   submit_v4.sh test   [--go]   bound-volume page slices, debug partition
#   submit_v4.sh chunk1 [--go]   chunk 1 only (largest bound volumes)
#   submit_v4.sh rest   [--go]   chunks 2..N
#   submit_v4.sh retry 19,20,23 [--go]   just the listed chunks
#
# Without --go it only prints the pre-flight evidence and the sbatch line.
# Run it on trig-login01, from the copy of the script the job will actually
# use -- the pre-flight is about *that* file, not the local one.
#
# Walltime for chunk stages comes from the measured elapsed time of the same
# chunk in the v2 run (job 912422, identical chunk files) x 2.0. That run had
# no headers and the old token cap; the Sep 14 test of chunk 30 with headers
# took 54:53 against v2's 53:25. x2.0 because a timeout loses the whole
# document in flight, and Slurm bills only the time actually used.
set -uo pipefail

BASE=/scratch/$USER/tropical
cd "$BASE" || exit 1
SCRIPT=run_chunk_trillium.slurm
V2_JOB=912422
STAGE="${1:-}"; GO="${2:-}"
if [ "$STAGE" = retry ]; then
    LIST="${2:-}"; GO="${3:-}"
    [[ "$LIST" =~ ^[0-9]+(,[0-9]+)*$ ]] || { echo "retry needs a chunk list, e.g. 19,20,23"; exit 1; }
fi

case "$STAGE" in
    test)   CHUNKDIR=$BASE/chunks_test; OUTDIR=$BASE/output_v4_test; PART=debug ;;
    chunk1) CHUNKDIR=$BASE/chunks;      OUTDIR=$BASE/output_v4;      PART=compute ;;
    rest)   CHUNKDIR=$BASE/chunks;      OUTDIR=$BASE/output_v4;      PART=compute ;;
    retry)  CHUNKDIR=$BASE/chunks;      OUTDIR=$BASE/output_v4;      PART=compute ;;
    *) sed -n '3,13p' "$0"; exit 1 ;;
esac

NCHUNKS=$(ls "$CHUNKDIR"/chunk_*.tsv 2>/dev/null | wc -l)
[ "$NCHUNKS" -gt 0 ] || { echo "no chunk files in $CHUNKDIR"; exit 1; }
case "$STAGE" in
    test)   ARRAY=1-$NCHUNKS; TASKS=$(seq 1 "$NCHUNKS") ;;
    chunk1) ARRAY=1;          TASKS=1 ;;
    rest)   ARRAY=2-$NCHUNKS%8; TASKS=$(seq 2 "$NCHUNKS") ;;
    retry)  ARRAY=$LIST;        TASKS=${LIST//,/ } ;;
esac

if [ "$STAGE" = test ]; then
    TIME=01:00:00
else
    # Longest v2 elapsed over the tasks being submitted, x2.0, rounded up.
    TIME=$(sacct -j "$V2_JOB" -X -n -P -o JobID,Elapsed | python3 -c '
import sys, math
want = set(sys.argv[1].split())
secs = []
for line in sys.stdin:
    jid, el = line.strip().split("|")
    if jid.split("_")[-1] in want:
        h, m, s = map(int, el.split(":"))
        secs.append(h*3600 + m*60 + s)
if len(secs) != len(want):
    sys.exit(f"v2 elapsed found for {len(secs)} of {len(want)} tasks")
t = math.ceil(max(secs) * 2.0 / 60)
print(f"{t//60:02d}:{t%60:02d}:00")' "$TASKS") || exit 1
fi

CONFIG=$(PRINT_CONFIG=1 bash "$SCRIPT")

echo "=== pre-flight: stage=$STAGE host=$(hostname) $(date -Is)"
echo "--- script actually submitted: $BASE/$SCRIPT"
md5sum "$SCRIPT" check_doc.py
grep -n -E '^(MAX_OUT|MAX_MODEL_LEN|CHANDRA_FLAGS)=|--max-model-len' "$SCRIPT"
echo "--- config the job will enforce: $CONFIG"
echo "--- chunks: $CHUNKDIR  ($NCHUNKS files, submitting $ARRAY)"
for t in $TASKS; do
    f=$CHUNKDIR/chunk_$(printf %03d "$t").tsv
    printf '    %s  docs=%s pages=%s\n' "$(basename "$f")" "$(wc -l < "$f")" "$(awk -F'\t' '{s+=$3} END {print s}' "$f")"
done
echo "--- outdir: $OUTDIR"
if [ -f "$OUTDIR/RUN_CONFIG" ]; then
    if [ "$(cat "$OUTDIR/RUN_CONFIG")" = "$CONFIG" ]; then echo "    RUN_CONFIG present, matches"
    else echo "    RUN_CONFIG MISMATCH: $(cat "$OUTDIR/RUN_CONFIG")"; exit 1; fi
elif [ -d "$OUTDIR" ] && [ -n "$(ls -A "$OUTDIR")" ]; then
    echo "    non-empty with no RUN_CONFIG -- refusing"; exit 1
else
    echo "    new; RUN_CONFIG will be written"
fi
echo "--- fair share: $(sshare -U -u "$USER" -n -P -o FairShare 2>/dev/null | tail -1)"

CMD=(sbatch --account=def-jic823 --partition="$PART" --time="$TIME" --array="$ARRAY"
     --job-name="tt-v4-$STAGE" --output="$BASE/logs/tt-v4-$STAGE-%A_%a.out"
     --export=ALL,CHUNKDIR="$CHUNKDIR",OUTDIR="$OUTDIR",BASE="$BASE" "$SCRIPT")
echo "--- ${CMD[*]}"

if [ "$GO" != "--go" ]; then echo "=== dry run; add --go to submit"; exit 0; fi
mkdir -p "$OUTDIR" "$BASE/logs"
[ -f "$OUTDIR/RUN_CONFIG" ] || echo "$CONFIG" > "$OUTDIR/RUN_CONFIG"
"${CMD[@]}"
