#!/bin/bash
# StrokeLab · instalación en el clúster (una sola vez). Uso, desde la carpeta strokelab:  bash cluster/instalar.sh
# Cuota de 20 GB: se instala sin caché de pip y con OpenCV sin interfaz gráfica (el servidor no tiene pantalla).
set -e
cd "$(dirname "$0")/.."
python3 -m venv venv
source venv/bin/activate
pip install --no-cache-dir --upgrade pip
pip install --no-cache-dir torch                       # en Linux, la versión de PyPI ya trae CUDA
pip install --no-cache-dir numpy pandas scipy scikit-learn matplotlib opencv-python-headless shap ultralytics huggingface_hub imageio-ffmpeg
pip uninstall -y opencv-python 2>/dev/null || true      # ultralytics puede instalar la versión con interfaz gráfica
pip install --no-cache-dir --force-reinstall --no-deps opencv-python-headless
echo; echo "Espacio usado en tu cuenta:"; du -sh "$HOME" 2>/dev/null
echo "Instalación terminada. Siguiente paso:  sbatch cluster/prueba_gpu.sbatch"
