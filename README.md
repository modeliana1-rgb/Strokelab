# StrokeLab

TFM · Máster en Inteligencia Artificial · Universidad Europea de Madrid.

Análisis biomecánico explicable de la natación a partir de vídeo. Detecta **cuándo aparece la fatiga** de un nadador y **por qué**, mediante Isolation Forest + SHAP sobre variables por ciclo de brazada.

## Arquitectura: dos verticales

| Vertical | Entrada → salida | Técnicas |
| --- | --- | --- |
| 1 · Visión | vídeo → 17 keypoints COCO por fotograma | MoveNet con recorte de seguimiento (comparado con YOLO-Pose), limpieza y suavizado Savitzky-Golay |
| 2 · Tabular | keypoints → ciclos → eficiencia y fatiga | Variables por ciclo, Isolation Forest, PELT, SHAP, XGBoost (estilo) |

El modelo hidrodinámico (F = ½·ρ·Cd·A·v²) es conocimiento previo del dominio y no forma parte de la IA.

## Uso local en CPU (recomendado)

```powershell
pip install --user --only-binary=:all: -r requirements.txt
python diagnostico.py                       # comprueba qué librerías funcionan en tu equipo
python analizar.py "C:\ruta\al\video.MP4" --nadador "Nadador A"
```

Qué hace, en orden:

1. **Pose 2D** con YOLOv8n-Pose (1 de cada 2 fotogramas; `--cada 1` para todos, `--modelo` para cambiar de modelo).
2. **Limpieza**: confianza, huecos de hasta 0,4 s y suavizado.
3. **3D con MotionBERT-Lite**: el nadador se gira a vertical antes de elevarlo, porque el modelo se entrenó con personas de pie. En vista lateral (por defecto) los ángulos se calculan en 2D y el 3D se guarda aparte (`*_3d`), porque la validación mostró que el 3D falla en las piernas bajo el agua; con `--vista otra` (frontal, oblicua) se usan los ángulos 3D. `python validar_3d.py <carpeta>` compara ambos. Con `--sin-3d` no se calcula el 3D.
4. **Medidas** (izquierda y derecha): codo, hombro, cadera, rodilla, alcance, asimetría, inclinación, amplitud de patada y patadas por ciclo.
5. **Ciclos de brazada y fatiga**: Isolation Forest, PELT (implementación propia, sin dependencias compiladas) y explicación SHAP.
6. **Vídeo anotado** con el panel de medidas (`--formato avi` si el mp4 no se abre en tu equipo).

Otras opciones:

- `--comparativa`: compara los modelos de pose en CPU (YOLOv8n/11n/8s, MoveNet, MediaPipe).
- `--desde-keypoints`: repite el análisis sin volver a extraer la pose.
- `--metros-encuadre`: calibración métrica con cámara fija (velocidad, DPS e Índice de Brazada).

Todos los vídeos de una vez (se puede dejar trabajando; si se corta, continúa donde iba):

```powershell
python lote.py --carpeta C:\Users\user\StrokeLab\videos --crear-lista   # crea videos\lista_videos.csv: revísala
python lote.py --carpeta C:\Users\user\StrokeLab\videos                 # analiza y une las sesiones
```

La lista indica nadador, estilo (`crol`, `espalda`, `mariposa`, `braza`), vista (`lateral` u `otra`) y sesión.
Salen `resumen_lote.csv`, `resumen_sesiones.csv` y `para_claude.zip` (todo menos los vídeos) en `..\resultados`.
Con un solo vídeo, `--estilo` fija cuántas brazadas forman un ciclo: 2 en crol y espalda, 1 en mariposa y braza.

Informe de un nadador y estilo (tras el lote): `python informe_nadador.py ..\resultados --nadador Aaron --estilo crol`.
Si YOLO pierde al nadador: `python probar_deteccion.py VIDEO --desde S --hasta S` compara `--imgsz 640/1280` y `--conf-det 0,25/0,10`.

Fatiga a lo largo de una sesión (varias pasadas del mismo nadador, en orden de grabación):

```powershell
python sesion.py ..\resultados\GX011614_Aaron ..\resultados\GX011617_Aaron ..\resultados\GX011618_Aaron --nadador "Aaron"
```

Modelo 3D: la primera vez se descarga de Hugging Face. Si falla, descarga `best_epoch.bin` de MotionBERT-Lite
([enlace oficial](https://1drv.ms/f/s!AvAdh0LSjEOlgT67igq_cIoYvO2y?e=bfEc73)) en `modelos/motionbert/best_epoch.bin`
o pásalo con `--motionbert RUTA`.

## Estructura

```
analizar.py                             # programa principal (local, CPU)
diagnostico.py                          # comprueba las librerías disponibles
strokelab/                              # pose, 3D (MotionBERT), medidas, fatiga y vídeo
strokelab/motionbert/                   # modelo DSTformer de MotionBERT (Apache 2.0)
tests/test_local.py                     # prueba del programa local con nadador sintético
tests/test_sesion.py                    # prueba del análisis por sesión (3 pasadas)
sesion.py                               # fatiga a lo largo de varias pasadas
notebooks/StrokeLab_v3_pipeline.ipynb   # versión anterior para Google Colab (GPU)
tools/build_notebook.py                 # genera el notebook (fuente de verdad del código)
tests/test_pipeline_sintetico.py        # prueba con un nadador sintético que se fatiga
tests/test_movenet_recorte.py           # prueba de coordenadas del seguidor MoveNet
tests/test_notebook_compila.py          # comprueba que todas las celdas son Python válido
```

## Ejecutar en Colab (versión anterior)

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
python tests/test_movenet_recorte.py
python tests/test_notebook_compila.py
```
