#!/bin/bash
#
# Submit Tropical Agriculturist volumes to Chandra 2 as bucketed SLURM arrays
# on 3g.40gb MIG slices.
#
# Resumable: a volume with non-empty Markdown is skipped, so re-running after
# failures submits only what is left.
#
# Two mechanisms carried over from the sessional_papers run, both earned the
# hard way:
#
#   * Concurrency is capped. Not politeness -- many array tasks pulling the
#     model off Lustre at once stretched vLLM load from ~6 min to 22-39, which
#     tripped the readiness timeout and looked like a crash.
#   * Overruns escalate. Each submission bumps a volume's attempt count and
#     places it one bucket higher next round, so a volume that times out at 2h
#     is retried at 4h, then 8h, then 16h, with nobody having to intervene.
#     This matters more here than there, because the MIG planning rate is an
#     estimate until calibrated.
#
# Usage:
#   bash 05_submit.sh --dry-run
#   bash 05_submit.sh
#   bash 05_submit.sh --bucket b4h
#   CONCURRENCY=8 bash 05_submit.sh
#
#   # Plato: one MIG slice at a time on a small shared cluster
#   BASE=/project/clifford/tropical ACCOUNT=hpc_p_clifford \
#     GPU_FLAG=--gres=gpu:3g.40gb:1 CONCURRENCY=1 JOBPREFIX=tap \
#     RUNNER=/project/clifford/tropical/run_volume_plato.slurm \
#     bash 05_submit.sh
#
set -euo pipefail

BASE="${BASE:-/project/def-jic823/tropical}"
MANIFEST="${MANIFEST:-$BASE/manifest.tsv}"
OUTDIR="${OUTDIR:-$BASE/output}"
CONCURRENCY="${CONCURRENCY:-12}"
ACCOUNT="${ACCOUNT:-def-jic823}"
# How this site asks for a GPU. Nibi wants --gpus=<type>:1; Plato wants
# --gres=gpu:3g.40gb:1 and **rejects an explicit --partition** ("not allowed to
# submit"), so the whole flag is passed in rather than assembled here.
GPU_FLAG="${GPU_FLAG:---gpus=${GPUSPEC:-nvidia_h100_80gb_hbm3_3g.40gb:1}}"
SUBMIT_LIMIT="${SUBMIT_LIMIT:-950}"   # MaxSubmitJobs is 1000; leave headroom
JOBPREFIX="${JOBPREFIX:-ta}"
RUNNER="${RUNNER:-$BASE/run_volume.slurm}"
# Extra sbatch flags for this site/slice, e.g. "--cpus-per-task=4 --mem=40G"
# when packing smaller MIG slices onto a node that has fewer CPUs than GPUs.
SBATCH_EXTRA="${SBATCH_EXTRA:-}"

DRY=0; ONLY_BUCKET=""
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY=1 ;;
        --bucket)  ONLY_BUCKET="${2:?--bucket needs a value}"; shift ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
    shift
done

[ -f "$MANIFEST" ] || { echo "No manifest at $MANIFEST -- run 04_manifest.py" >&2; exit 1; }
[ -f "$RUNNER" ]   || { echo "No runner at $RUNNER" >&2; exit 1; }
mkdir -p "$OUTDIR" "$BASE/logs" "$BASE/tasklists"

is_done() {
    find "$OUTDIR/$1" -name '*.md' -size +1k -print -quit 2>/dev/null | grep -q .
}

# Tags that already have a queued or running array task.
#
# Without this the script is a footgun: it skips only *finished* work, so
# re-running it while a round is still in the queue resubmits every
# outstanding volume as a duplicate job -- and also bumps each one's attempt
# count, pushing it into a longer bucket for no reason. Reconstructed by
# mapping each live array job's task ids back through the tasklist snapshot
# that was saved under its job id at submission time.
QUEUED_TAGS="$(mktemp)"
# PENDING_ATTEMPTS is created further down; guard against an early exit
# between here and there, which under `set -u` would make the trap itself fail.
trap 'rm -f "${PENDING_ATTEMPTS:-}" "${QUEUED_TAGS:-}"' EXIT

collect_queued() {
    command -v squeue >/dev/null 2>&1 || return 0
    local jid tasks snap
    # %F is the array job id, %K the task id (or range for pending arrays).
    squeue -u "$USER" -h -o '%F %K' -t PENDING,RUNNING,SUSPENDED 2>/dev/null |
    while read -r jid tasks; do
        [ -n "$jid" ] || continue
        # `|| true` matters: when the glob matches nothing, ls exits non-zero,
        # pipefail propagates that through `| head -1`, and the command
        # substitution hands that status to the assignment -- which under
        # `set -e` kills the script silently, with no output at all. This only
        # shows up when a live job has no tasklist snapshot (e.g. one submitted
        # by hand), which is why it survived every run on Nibi.
        snap=$(ls "$BASE/tasklists/"*"-${jid}.tsv" 2>/dev/null | head -1) || true
        [ -n "$snap" ] || continue
        # A pending array reports its whole remaining range (e.g. "1-219%8"),
        # so treat every tag in the snapshot as still in flight; expanding the
        # range exactly buys nothing and risks under-counting.
        cut -f1 "$snap"
    done | sort -u > "$QUEUED_TAGS"
    local n
    n=$(wc -l < "$QUEUED_TAGS")
    [ "$n" -gt 0 ] && echo "$n document(s) already queued or running; skipping those"
    return 0
}

is_queued() {
    [ -s "$QUEUED_TAGS" ] && grep -qxF "$1" "$QUEUED_TAGS"
}

collect_queued

ATTEMPTS="$BASE/attempts.tsv"
touch "$ATTEMPTS"

# Snapshot attempt counts BEFORE deciding any buckets. Reading and writing the
# same file inside the bucket loop makes a volume just submitted to b2h look
# like a b4h retry moments later, so every subsequent bucket picks it up again
# -- the cascade that once put 1050 jobs over the 1000-job submit limit.
declare -A ATTEMPT_OF=()
while IFS=$'\t' read -r t n; do
    [ -n "$t" ] && ATTEMPT_OF["$t"]="$n"
done < "$ATTEMPTS"

PENDING_ATTEMPTS="$(mktemp)"

merge_attempts() {
    [ -s "$PENDING_ATTEMPTS" ] || return 0
    awk -F'\t' '{a[$1]=$2} END {for (k in a) printf "%s\t%s\n", k, a[k]}' \
        "$ATTEMPTS" "$PENDING_ATTEMPTS" > "$ATTEMPTS.tmp"
    mv "$ATTEMPTS.tmp" "$ATTEMPTS"
}

BUCKET_ORDER=(b2h b4h b8h b16h)

effective_bucket() {
    local base_bucket="$1" tries="$2" i idx=0
    for i in "${!BUCKET_ORDER[@]}"; do
        [ "${BUCKET_ORDER[$i]}" = "$base_bucket" ] && idx=$i && break
    done
    idx=$((idx + tries))
    [ "$idx" -ge "${#BUCKET_ORDER[@]}" ] && idx=$(( ${#BUCKET_ORDER[@]} - 1 ))
    echo "${BUCKET_ORDER[$idx]}"
}

walltime_for_bucket() {
    case "$1" in
        b2h)  echo "2:00:00"  ;;
        b4h)  echo "4:00:00"  ;;
        b8h)  echo "8:00:00"  ;;
        b16h) echo "16:00:00" ;;
    esac
}

submitted_total=0
for bucket in "${BUCKET_ORDER[@]}"; do
    [ -z "$ONLY_BUCKET" ] || [ "$ONLY_BUCKET" = "$bucket" ] || continue

    # Unique per invocation, and never reused. A fixed name (tasklists/$bucket.tsv)
    # is a live dependency of every array already running against it: SLURM reads
    # it at task start, not at submit. A later pass -- including a --dry-run,
    # which has no business mutating anything -- would truncate or delete it and
    # every queued task would die with "no task at line N".
    tasklist="$BASE/tasklists/${JOBPREFIX}-${bucket}-$(date +%s)-$$.tsv"
    : > "$tasklist"

    while IFS=$'\t' read -r tag pdf pages b wt; do
        [ "${tag#\#}" = "$tag" ] || continue      # skip header
        is_done "$tag" && continue
        is_queued "$tag" && continue
        tries="${ATTEMPT_OF[$tag]:-0}"
        [ "$(effective_bucket "$b" "$tries")" = "$bucket" ] || continue
        printf '%s\t%s\n' "$tag" "$pdf" >> "$tasklist"
        printf '%s\t%s\n' "$tag" "$((tries + 1))" >> "$PENDING_ATTEMPTS"
    done < "$MANIFEST"

    n=$(wc -l < "$tasklist")
    if [ "$n" -eq 0 ]; then
        echo "$bucket: nothing outstanding"
        rm -f "$tasklist"          # safe: unique name, nothing references it
        continue
    fi
    if [ $((submitted_total + n)) -gt "$SUBMIT_LIMIT" ]; then
        echo "$bucket: $n documents would exceed the ${SUBMIT_LIMIT}-job submit" \
             "limit (already staged $submitted_total). Submit the rest once this" \
             "round drains."
        rm -f "$tasklist"
        break
    fi

    walltime="$(walltime_for_bucket "$bucket")"
    echo "$bucket: $n documents outstanding, walltime $walltime, concurrency %$CONCURRENCY"
    if [ "$DRY" -eq 1 ]; then
        head -3 "$tasklist" | sed 's/^/    /'
        [ "$n" -gt 3 ] && echo "    ... and $((n-3)) more"
        rm -f "$tasklist"
        continue
    fi

    jid=$(sbatch --parsable \
        --account="$ACCOUNT" \
        --job-name="$JOBPREFIX-$bucket" \
        $GPU_FLAG $SBATCH_EXTRA \
        --array="1-${n}%${CONCURRENCY}" \
        --time="$walltime" \
        --output="$BASE/logs/${JOBPREFIX}-${bucket}-%A_%a.out" \
        --export=ALL,TASKLIST="$tasklist",OUTDIR="$OUTDIR",BASE="$BASE" \
        "$RUNNER")
    echo "  submitted array $jid"
    # Snapshot the tasklist under the job id: the per-bucket file is rewritten
    # every run, so without this the array-task -> volume mapping is lost as
    # soon as the next round is submitted.
    cp "$tasklist" "$BASE/tasklists/${JOBPREFIX}-${bucket}-${jid}.tsv"
    printf '%s\t%s\t%s\t%s\n' "$(date -Is)" "$bucket" "$jid" "$n" >> "$BASE/submissions.log"
    submitted_total=$((submitted_total + n))
done

[ "$DRY" -eq 1 ] || merge_attempts
echo ""
echo "total documents submitted: $submitted_total"
[ "$DRY" -eq 1 ] || echo "monitor: bash $BASE/06_status.sh"
