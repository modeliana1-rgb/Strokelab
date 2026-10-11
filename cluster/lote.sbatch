#!/bin/bash
# StrokeLab · análisis de todos los vídeos con GPU. Uso, desde la carpeta strokelab:  sbatch cluster/lote.sbatch
# Ver el avance:  tail -f lote_<número>.log      ·  Ver la cola:  squeue -u $USER      ·  Cancelar:  scancel <número>
# Es reanudable: si se corta, vuelve a lanzarlo y sigue por donde iba (quita entonces --rehacer-pose).
#SBATCH --job-name=strokelab_lote
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=24:00:00
#SBATCH --output=lote_%j.log
cd "$SLURM_SUBMIT_DIR"
source venv/bin/activate
export MPLBACKEND=Agg PYTHONUNBUFFERED=1
nvidia-smi --query-gpu=name,memory.total --format=csv
python3 lote.py --carpeta ../videos --imgsz 1280 --rehacer-pose
