#!/bin/bash
# StrokeLab · análisis de UN vídeo con GPU. Uso, desde la carpeta strokelab:
#   sbatch cluster/video.sbatch ../Ian_Thorpe.mp4 Thorpe crol
# (vídeo, nombre del nadador y estilo; el estilo puede ser auto). Ver el avance: tail -f video_<número>.log
#SBATCH --job-name=strokelab_video
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=04:00:00
#SBATCH --output=video_%j.log
cd "$SLURM_SUBMIT_DIR"
source venv/bin/activate
export MPLBACKEND=Agg PYTHONUNBUFFERED=1
nvidia-smi --query-gpu=name,memory.total --format=csv
python3 analizar.py "$1" --nadador "${2:-Nadador}" --estilo "${3:-crol}" --vista auto --sin-3d --cada 1 --panel completo
