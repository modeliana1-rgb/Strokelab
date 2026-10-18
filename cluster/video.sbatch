#!/bin/bash
# StrokeLab · análisis de UN vídeo con GPU. Uso, desde la carpeta strokelab:
#   sbatch cluster/video.sbatch ../videos/Ian_Thorpe.mp4 Thorpe crol [modelo] [carpeta de salida]
# (vídeo, nombre del nadador, estilo (puede ser auto) y, opcional, modelo de pose, p. ej. el ajustado
#  ../modelos_pose/final/weights/last.pt, y carpeta de resultados). Ver el avance: tail -f video_<número>.log
#SBATCH --job-name=strokelab_video
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=04:00:00
#SBATCH --output=video_%j.log
cd "$SLURM_SUBMIT_DIR"
if [ -f venv/bin/activate ]; then source venv/bin/activate; else source ../venv/bin/activate; fi
export MPLBACKEND=Agg PYTHONUNBUFFERED=1
nvidia-smi --query-gpu=name,memory.total --format=csv
python3 analizar.py "$1" --nadador "${2:-Nadador}" --estilo "${3:-crol}" --vista auto --sin-3d --cada 1 --panel completo \
  --modelo "${4:-yolov8n-pose}" ${5:+--salida "$5"}
