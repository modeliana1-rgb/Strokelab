#!/bin/bash
# StrokeLab · ajuste fino con modelos de pose más grandes (YOLOv8s y YOLOv8m), mismos 4 pliegues que el n.
# Uso, desde la carpeta strokelab:  sbatch cluster/entrenar_pose_grandes.sbatch   ·  avance: tail -f entrenar_grandes_<n>.log
# Salida: ../modelos_pose_s/comparacion_pose.json y ../modelos_pose_m/comparacion_pose.json
#SBATCH --job-name=strokelab_pose_sm
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=12:00:00
#SBATCH --output=entrenar_grandes_%j.log
cd "$SLURM_SUBMIT_DIR"
if [ -f venv/bin/activate ]; then source venv/bin/activate; else source ../venv/bin/activate; fi
export MPLBACKEND=Agg PYTHONUNBUFFERED=1
nvidia-smi --query-gpu=name,memory.total --format=csv
for T in s m; do
  BASE=yolov8${T}-pose.pt
  [ -f ../$BASE ] && BASE=../$BASE                     # si ya está descargado en StrokeLab/
  python3 entrenar_pose.py --datos ../datos_pose --pliegues 4 --epocas 80 --dispositivo 0 --base $BASE --salida ../modelos_pose_$T
done
