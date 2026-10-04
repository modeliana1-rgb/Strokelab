# StrokeLab

TFM · Máster en Inteligencia Artificial · Universidad Europea de Madrid.

Análisis biomecánico explicable de la natación a partir de vídeo. Detecta **cuándo aparece la fatiga** de un nadador y **por qué**, mediante Isolation Forest + SHAP sobre variables por ciclo de brazada.

## Arquitectura: dos verticales

| Vertical | Entrada → salida | Técnicas |
| --- | --- | --- |
| 1 · Visión | vídeo → 17 keypoints COCO por fotograma | Comparativa YOLOv8/YOLO11-Pose vs MoveNet, limpieza y suavizado Savitzky-Golay |
| 2 · Tabular | keypoints → ciclos → eficiencia y fatiga | Variables por ciclo, Isolation Forest, PELT, SHAP, XGBoost (estilo) |

El modelo hidrodinámico (F = ½·ρ·Cd·A·v²) es conocimiento previo del dominio y no forma parte de la IA.

## Estructura

```
notebooks/StrokeLab_v3_pipeline.ipynb   # pipeline completo para Google Colab (GPU)
tools/build_notebook.py                 # genera el notebook (fuente de verdad del código)
tests/test_pipeline_sintetico.py        # prueba con un nadador sintético que se fatiga
```

## Ejecutar en Colab

1. Abre `notebooks/StrokeLab_v3_pipeline.ipynb` en Colab (Archivo → Abrir cuaderno → GitHub).
2. Entorno de ejecución → Cambiar tipo → **GPU (T4)**.
3. En la celda **CONFIGURACIÓN**, pon `VIDEO_PATH`, `OUT_DIR` y, si la cámara está fija, `METROS_ANCHO_ENCUADRE`.
4. Ejecutar todas. Los resultados (CSV, JSON, figuras PNG y vídeo anotado) quedan en `OUT_DIR`.

## Desarrollo

Edita `tools/build_notebook.py` (no el `.ipynb` a mano) y regenera el notebook:

```bash
pip install -r requirements.txt
python tools/build_notebook.py
MPLBACKEND=Agg python tests/test_pipeline_sintetico.py
```
