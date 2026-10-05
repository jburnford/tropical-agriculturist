#!/bin/bash
#
# One-shot survey of Trillium, run on a login node the moment the account lands.
# Answers everything needed to port the Chandra 2 pipeline without guessing.
#
# SciNet systems differ from the rest of the Alliance in ways that have bitten
# this project before on other clusters: compute nodes may have no outbound
# internet (so the model must be pre-staged), home quotas are small (so the
# ~10 GB model cache must not live there), and the module stack may not be the
# standard CC one. Each is checked rather than assumed.
#
#   ssh trillium.alliancecan.ca 'bash -s' < trillium_probe.sh
#
echo "=============== IDENTITY ==============="
echo "host: $(hostname)   user: $USER   date: $(date -Is)"
sacctmgr -nP show assoc user=$USER format=Account,QOS 2>/dev/null | sort -u

echo; echo "=============== FAIR SHARE (the decisive number) ==============="
sshare -U -u $USER -o Account,RawShares,NormShares,RawUsage,EffectvUsage,FairShare 2>/dev/null | head -8

echo; echo "=============== PRIORITY WEIGHTS ==============="
scontrol show config 2>/dev/null | grep -iE "PriorityWeightFairshare|PriorityWeightAge|PriorityDecayHalfLife|MaxSubmitJobs"

echo; echo "=============== GPU INVENTORY ==============="
sinfo -h -o "%G" 2>/dev/null | tr ',' '\n' | sed 's/(.*//' | sort -u | head
echo "--- partitions ---"
sinfo -h -o "%P %a %l %D" 2>/dev/null | head -8
echo "--- queue depth for gpu ---"
squeue -h -t PENDING 2>/dev/null | wc -l; echo "  pending (all users)"

echo; echo "=============== STORAGE / QUOTA ==============="
diskusage_report 2>/dev/null | head -8 || { quota -s 2>/dev/null | head -5; }
echo "--- env paths ---"
for v in HOME SCRATCH PROJECT ARCHIVE BB_JOB_DIR; do
    eval "p=\${$v:-}"; [ -n "$p" ] && echo "  $v=$p"
done

echo; echo "=============== SOFTWARE ==============="
echo "module system: $(command -v module >/dev/null && echo Lmod/modules || echo none)"
python3 -V 2>&1
echo "--- python modules available ---"
module -t spider python 2>&1 | grep -E "^python/" | head -6
echo "--- cuda ---"
module -t spider cuda 2>&1 | grep -E "^cuda/" | head -6
echo "--- apptainer/singularity ---"
command -v apptainer >/dev/null && apptainer --version || module -t spider apptainer 2>&1 | head -3

echo; echo "=============== OUTBOUND INTERNET (login node) ==============="
curl -s -o /dev/null -w "  huggingface.co  HTTP %{http_code} in %{time_total}s\n" --max-time 20 https://huggingface.co 2>&1
curl -s -o /dev/null -w "  pypi.org        HTTP %{http_code} in %{time_total}s\n" --max-time 20 https://pypi.org 2>&1

echo; echo "=============== EXISTING WORK ==============="
ls -d ~/projects/*/ 2>/dev/null | head -5
find ~ -maxdepth 3 -iname "*chandra*" -o -maxdepth 3 -iname "*hf_cache*" 2>/dev/null | head -5
echo "done."
