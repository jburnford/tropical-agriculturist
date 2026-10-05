#!/bin/bash
# Tesseract word boxes (TSV) for the side-by-side table pages (tsplit.py input).
# Submit from tri-login01:  sbatch repair/vsplit/tess_boxes.slurm
#SBATCH --account=def-jic823
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=192
#SBATCH --time=00:30:00
#SBATCH --job-name=tt-vboxes
#SBATCH --output=/scratch/jic823/tropical/logs/tt-vboxes-%j.out
module load apptainer
cd /scratch/jic823/tropical
export OMP_THREAD_LIMIT=1
mkdir -p repair/vsplit/tess
awk -F'\t' '$3!="other"{printf "%s\t%04d\n",$1,$2}' repair/vsplit/page_types.tsv |
  xargs -P 96 -L 1 bash -c 'o=repair/vsplit/tess/${0}_p${1}; [ -s $o.tsv ] || apptainer exec /scratch/jic823/containers/tesseract.sif tesseract leaves/full/$0/p$1.png $o --psm 3 tsv >/dev/null 2>&1 || echo "FAIL $0 $1"'
echo "[job] tsv files: $(ls repair/vsplit/tess/*.tsv | wc -l)"
