#!/bin/bash
# Stage 4 audit: Tesseract over every page of the corpus (Trillium CPU cluster).
# Submit from tri-login01:  sbatch audit_tess.slurm
#SBATCH --account=def-jic823
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=192
#SBATCH --time=01:00:00
#SBATCH --job-name=tt-auditM
#SBATCH --output=/scratch/jic823/tropical/logs/tt-auditM-%j.out
module load apptainer
cd /scratch/jic823/tropical
export MIRROR=1
/scratch/jic823/chandra/venv/bin/python audit_tess.py chunks stage4/audit_mirror 190
