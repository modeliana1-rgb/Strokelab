#!/bin/bash
# StrokeLab · ajuste fino de YOLOv8n-Pose con nadadores (4 pliegues agrupados por vídeo) y comparación con el original.
# Antes:  python3 preparar_datos_pose.py ../datos_nadadores/* --salida ../datos_pose --pliegues 4
# Uso, desde la carpeta strokelab:  sbatch cluster/entrenar_pose.sbatch      ·  avance: tail -f entrenar_pose_<n>.log
#SBATCH --job-name=strokelab_pose
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=12:00:00
#SBATCH --output=entrenar_pose_%j.log
cd "$SLURM_SUBMIT_DIR"
source venv/bin/activate
export MPLBACKEND=Agg PYTHONUNBUFFERED=1
python3 entrenar_pose.py --datos ../datos_pose --pliegues 4 --epocas 80 --dispositivo 0 --salida ../modelos_pose
