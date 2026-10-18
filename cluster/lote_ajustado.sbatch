#!/bin/bash
# StrokeLab · todos los vídeos con YOLO ajustado con nadadores. Uso, desde la carpeta strokelab:
#   sbatch cluster/lote_ajustado.sbatch          ·  avance: tail -f lote_ajustado_<número>.log
# 1) Si no existe, entrena el modelo final con las 405 imágenes (necesita ../datos_pose de preparar_datos_pose.py).
# 2) Analiza la lista de ../videos con ese modelo (imgsz 640) y guarda en ../resultados_ajustado (los originales no se tocan).
# Es reanudable: si se corta, vuelve a lanzarlo y sigue por donde iba.
#SBATCH --job-name=strokelab_ajustado
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=24:00:00
#SBATCH --output=lote_ajustado_%j.log
cd "$SLURM_SUBMIT_DIR"
if [ -f venv/bin/activate ]; then source venv/bin/activate; else source ../venv/bin/activate; fi
export MPLBACKEND=Agg PYTHONUNBUFFERED=1
nvidia-smi --query-gpu=name,memory.total --format=csv
MODELO=../modelos_pose/final/weights/last.pt
if [ ! -f "$MODELO" ]; then
  python3 entrenar_pose.py --datos ../datos_pose --final --epocas 60 --dispositivo 0 --salida ../modelos_pose || exit 1
fi
python3 lote.py --carpeta ../videos --resultados ../resultados_ajustado --modelo "$MODELO" --imgsz 640
