#!/bin/bash
#
# Progress report for the Tropical Agriculturist OCR run.
#
# Usage: bash 06_status.sh [--failed]
#   --failed   list the documents that have been attempted but produced nothing
#
# Distinguishes queued work from failed work. This matters: 05_submit.sh
# records an attempt when a volume is *submitted*, not when it fails, so a
# check based on the attempts file alone reports a freshly queued round of 269
# documents as "attempted, no output" -- indistinguishable from 269 failures.
#
set -uo pipefail

BASE="${BASE:-/project/def-jic823/tropical}"
# Aggregate across every per-feeder manifest (manifest.<prefix>.tsv), not just
# the default one. With two feeders running disjoint volume ranges, reading a
# single manifest reports one feeder's slice of the work as if it were the
# whole job -- which understated progress badly enough to look like a failure.
if [ -n "${MANIFEST:-}" ]; then
    MANIFESTS="$MANIFEST"
else
    MANIFESTS=$(ls "$BASE"/manifest.*.tsv 2>/dev/null)
    [ -n "$MANIFESTS" ] || MANIFESTS="$BASE/manifest.tsv"
fi
OUTDIR="${OUTDIR:-$BASE/output}"
JOBPREFIX="${JOBPREFIX:-ta}"

SHOW_FAILED=0
[ "${1:-}" = "--failed" ] && SHOW_FAILED=1

MERGED="$(mktemp)"
for m in $MANIFESTS; do [ -f "$m" ] && grep -v '^#' "$m"; done | sort -u > "$MERGED"
[ -s "$MERGED" ] || { echo "No manifest found under $BASE" >&2; exit 1; }

# Tags with a live array task, mapped back through the tasklist snapshots
# saved under each job id at submission time.
QUEUED_TAGS="$(mktemp)"
trap 'rm -f "${QUEUED_TAGS:-}" "${MERGED:-}"' EXIT
if command -v squeue >/dev/null 2>&1; then
    squeue -u "$USER" -h -o '%F %K' -t PENDING,RUNNING,SUSPENDED 2>/dev/null |
    while read -r jid _tasks; do
        [ -n "$jid" ] || continue
        # `|| true` matters: when the glob matches nothing, ls exits non-zero,
        # pipefail propagates that through `| head -1`, and the command
        # substitution hands that status to the assignment -- which under
        # `set -e` kills the script silently, with no output at all. This only
        # shows up when a live job has no tasklist snapshot (e.g. one submitted
        # by hand), which is why it survived every run on Nibi.
        snap=$(ls "$BASE/tasklists/"*"-${jid}.tsv" 2>/dev/null | head -1) || true
        # `if`, not `&&`: a bare test is the last command in this loop body, so
        # when no snapshot exists it returns 1, the while-subshell exits
        # non-zero, pipefail propagates that, and `set -e` kills the script
        # with no output at all. An `if` with no else always returns 0.
        if [ -n "$snap" ]; then cut -f1 "$snap"; fi
    done | sort -u > "$QUEUED_TAGS"
fi

total=0; done_n=0; queued_n=0; done_pages=0; total_pages=0; queued_pages=0
failed_list=()
while IFS=$'\t' read -r tag pdf pages bucket wt; do
    [ "${tag#\#}" = "$tag" ] || continue
    total=$((total + 1))
    total_pages=$((total_pages + pages))
    if find "$OUTDIR/$tag" -name '*.md' -size +1k -print -quit 2>/dev/null | grep -q .; then
        done_n=$((done_n + 1))
        done_pages=$((done_pages + pages))
    elif [ -s "$QUEUED_TAGS" ] && grep -qxF "$tag" "$QUEUED_TAGS"; then
        queued_n=$((queued_n + 1))
        queued_pages=$((queued_pages + pages))
    elif [ -d "$OUTDIR/$tag" ] || grep -qxF "$tag" <(cut -f1 "$BASE/attempts.tsv" 2>/dev/null) 2>/dev/null; then
        # Attempted at some point, not currently queued, no usable output.
        failed_list+=("$tag")
    fi
done < "$MERGED"

pct() { [ "$2" -gt 0 ] && echo $((100 * $1 / $2)) || echo 0; }

echo "Tropical Agriculturist - Chandra 2 OCR"
echo "======================================"
printf 'done        : %4d/%d documents (%d%%)   %d/%d pages (%d%%)\n' \
    "$done_n" "$total" "$(pct "$done_n" "$total")" \
    "$done_pages" "$total_pages" "$(pct "$done_pages" "$total_pages")"
printf 'in queue    : %4d documents (%d pages)\n' "$queued_n" "$queued_pages"
printf 'needs retry : %4d documents\n' "${#failed_list[@]}"
if [ "${#failed_list[@]}" -gt 0 ]; then
    echo "              (run 05_submit.sh to resubmit these one bucket higher)"
fi
echo ""

if command -v squeue >/dev/null 2>&1; then
    echo "queue:"
    # Match any feeder prefix (ta-, tap-, tab-), not just $JOBPREFIX: two
    # feeders on one cluster use different prefixes and a single-prefix filter
    # silently reports an empty queue while jobs are plainly running.
    squeue -u "$USER" -o '%.14i %.12j %.8T %.10M %.10l %R' 2>/dev/null \
        | grep -E "JOBID|[[:space:]]${JOBPREFIX%%-*}[a-z]*-" \
        || echo "  (no jobs queued or running)"
    echo ""
fi

# Observed throughput, which is the number that decides whether the walltime
# buckets in 04_manifest.py were budgeted correctly.
if command -v sacct >/dev/null 2>&1 && [ "$done_n" -gt 0 ]; then
    echo "observed throughput (completed tasks):"
    sacct -u "$USER" -X -n -P -o JobID,Elapsed,State 2>/dev/null \
        | awk -F'|' '$3=="COMPLETED"' > "$QUEUED_TAGS.sacct"
    awk -F'\t' '{print $1"\t"$3}' "$MERGED" > "$QUEUED_TAGS.pages"
    python3 - "$BASE" "$QUEUED_TAGS.sacct" "$QUEUED_TAGS.pages" <<'PY' 2>/dev/null || echo "  (could not compute)"
import glob, re, sys
base, sacct_f, pages_f = sys.argv[1:4]
pages = dict(l.rstrip("\n").split("\t") for l in open(pages_f) if "\t" in l)
tl = {}
for p in glob.glob(f"{base}/tasklists/*-*.tsv"):
    m = re.search(r"-(\d+)\.tsv$", p)
    if m:
        tl[m.group(1)] = [l.split("\t")[0] for l in open(p) if l.strip()]
rates = []
for line in open(sacct_f):
    jid, elapsed, _ = line.rstrip("\n").split("|")
    if "_" not in jid:
        continue
    arr, idx = jid.split("_", 1)
    tags = tl.get(arr)
    if not tags or not idx.isdigit():
        continue
    i = int(idx)
    if not (1 <= i <= len(tags)):
        continue
    p = pages.get(tags[i - 1])
    if not p:
        continue
    parts = [int(x) for x in elapsed.split(":")]
    mins = (parts[0] * 60 + parts[1] + parts[2] / 60) if len(parts) == 3 else 0
    if mins > 0:
        rates.append(int(p) / mins)
if rates:
    rates.sort()
    n = len(rates)
    print(f"  {n} task(s): min {rates[0]:.1f}  p10 {rates[int(.1*n)]:.1f}  "
          f"median {rates[n//2]:.1f}  max {rates[-1]:.1f} pages/min")
    print(f"  budgeted at 9.2 pages/min (p10); re-run 04_manifest.py --rate "
          f"{rates[int(.1*n)]:.1f} to re-bucket")
else:
    print("  (no joinable completed tasks yet)")
PY
    rm -f "$QUEUED_TAGS.sacct" "$QUEUED_TAGS.pages"
    echo ""
fi

if [ -f "$BASE/submissions.log" ]; then
    echo "last 5 submissions:"
    tail -5 "$BASE/submissions.log" | sed 's/^/  /'
    echo ""
fi

if [ "$SHOW_FAILED" -eq 1 ] && [ "${#failed_list[@]}" -gt 0 ]; then
    echo "attempted but no markdown:"
    for t in "${failed_list[@]}"; do
        tries=$(grep -P "^\Q$t\E\t" "$BASE/attempts.tsv" 2>/dev/null | cut -f2 | tail -1)
        echo "  $t (attempts: ${tries:-0})"
    done
    echo ""
fi

[ -d "$OUTDIR" ] && echo "output size: $(du -sh "$OUTDIR" 2>/dev/null | cut -f1)"
