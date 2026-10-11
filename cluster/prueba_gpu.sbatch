#!/bin/bash
# StrokeLab · comprueba que el nodo de cálculo ve la GPU (tarda 1-2 minutos). Uso:  sbatch cluster/prueba_gpu.sbatch
#SBATCH --job-name=strokelab_prueba
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=prueba_gpu_%j.log
cd "$SLURM_SUBMIT_DIR"
source venv/bin/activate
nvidia-smi
python3 diagnostico.py
