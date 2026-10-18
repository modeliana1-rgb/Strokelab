#!/bin/bash
# StrokeLab · ajuste fino de YOLOv8n-Pose con las imágenes reales (Roboflow) + sintéticas de SwimXYZ SOLO en entrenamiento.
# Los pliegues de prueba son los mismos que sin SwimXYZ (misma semilla): resultados comparables.
# Antes: subir ../swimxyz_yolo (salida de convertir_swimxyz.py). Uso: sbatch cluster/entrenar_pose_swimxyz.sbatch
#SBATCH --job-name=strokelab_swimxyz
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=12:00:00
#SBATCH --output=entrenar_swimxyz_%j.log
cd "$SLURM_SUBMIT_DIR"
if [ -f venv/bin/activate ]; then source venv/bin/activate; else source ../venv/bin/activate; fi
export MPLBACKEND=Agg PYTHONUNBUFFERED=1
nvidia-smi --query-gpu=name,memory.total --format=csv
python3 preparar_datos_pose.py ../datos_nadadores/deepdive --solo-entrenamiento ../swimxyz_yolo --salida ../datos_pose_swimxyz --pliegues 4 || exit 1
python3 entrenar_pose.py --datos ../datos_pose_swimxyz --pliegues 4 --epocas 80 --dispositivo 0 --salida ../modelos_pose_swimxyz
