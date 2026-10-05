#!/bin/bash
# Array 1032618 status + per-part progress on Trillium (run locally; needs the ControlMaster).
ssh -o BatchMode=yes trillium-gpu.scinet.utoronto.ca '
squeue -u jic823 -o "%.14i %.8T %.10M %R" | head -6
sacct -j 1032618 -X -o JobID,State,Elapsed -n 2>/dev/null | sort | uniq -c | sort -rn | head -8
cd /scratch/jic823/tropical/ner && for f in out/part_*.jsonl; do n=$(wc -l < $f); t=$(wc -l < jobs/$(basename $f)); echo "$(basename $f) $n/$t"; done 2>/dev/null | column -c 120'
