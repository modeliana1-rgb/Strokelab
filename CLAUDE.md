# StrokeLab · contexto para Claude

TFM de Diana Cruz (Máster en IA, Universidad Europea de Madrid). Entrega final: **15 de octubre de 2026**.
Sistema que analiza vídeo de natación y responde al entrenador: eficiencia de la brazada, **en qué momento
aparece la fatiga y por qué** (SHAP), y medidas de codos, hombros, caderas, rodillas y pies.

## Cómo se trabaja

- Todo se ejecuta **en local, en CPU**, en el portátil personal de Diana (Windows). No usar Colab salvo que lo pida.
- Programa principal: `python analizar.py "<vídeo>" --nadador "<nombre>"` (ver README para opciones).
- Pruebas antes de cada commit: `python tests/test_local.py` (y `tests/test_movenet_recorte.py`).
- Responder siempre en español. Explicar las decisiones técnicas en lenguaje claro: Diana las defiende ante un tribunal.
- No inventar resultados: lo que no se haya medido se marca como pendiente.

## Indicaciones del director (1 sept 2026) y cómo se cumplen

| Indicación | Implementación |
| --- | --- |
| La explicabilidad (SHAP) es lo más importante | `strokelab/fatiga.py`: Isolation Forest sobre el estado fresco del propio nadador + TreeSHAP + explicación en texto |
| 2 verticales de IA: Visión y Tabulares | Visión: `pose.py` (2D) + `lift3d.py` (3D). Tabular: `medidas.py` + `fatiga.py` |
| Modos diferenciados (vídeo, tabular, audio) | Vídeo y tabular implementados; audio es trabajo futuro |
| Modelo hidrodinámico en la Introducción (no es IA) | Solo en la memoria (Cap. 1); la potencia no es variable del modelo |
| Optimizar YOLO (investigar MoveNet, ViTPose) | `--comparativa` mide en CPU YOLOv8n/11n/8s, MoveNet y MediaPipe; elegido YOLOv8n; ViTPose como trabajo futuro |

## Decisiones tomadas (y por qué)

- **Pose 2D: YOLOv8n-Pose en CPU.** En el vídeo real (GX011615, 5K, 34 s, subacuático lateral), con fotogramas
  repartidos por todo el vídeo: YOLO detecta 47-72 % con confianza 0,73-0,77; MoveNet 35-48 % con 0,34-0,37.
  Con YOLO salieron 15 ciclos válidos frente a 3 con MoveNet. MoveNet se eligió antes por fluidez en CPU, pero el
  vídeo anotado se genera offline y se reproduce fluido con cualquier modelo. MoveNet sigue como opción (`--modelo`).
- **3D con MotionBERT-Lite se mantiene** (hay vídeos frontales y de varios ángulos). Adaptación: cada fotograma se
  centra en la pelvis y se gira para que el tronco quede vertical (MotionBERT se entrenó con personas de pie), y la
  escala se normaliza por el tamaño del cuerpo. Los ángulos articulares no cambian con el giro.
  **Pendiente: validar la calidad 3D con los pesos reales** (comparar ángulos 2D vs 3D en vista lateral).
- **Filtro de plausibilidad anatómica** (`medidas.py`): tronco fuera de [0,5, 2] × mediana, segmentos de brazo y
  pierna implausibles, codos < 25°. Motivo: bajo el agua el modelo coloca a veces la cadera sobre el hombro.
- **Fatiga por ciclo de brazada**, comparando con el primer 30 % de ciclos del propio nadador; inicio = 3 ciclos
  seguidos por encima del percentil 95 de la fase fresca; contraste con PELT.
- Variables redundantes fuera del modelo (v = SR·DPS; potencia ∝ v³).
- El 99,99 % de accuracy de versiones antiguas era fuga de datos; la clasificación de estilo usa GroupKFold por vídeo.

## Datos (Google Drive de Diana)

- `Videos_TFM/Nadador A/`: GX011615.MP4 (34 s, una pasada, sirve para validar pero no para fatiga), GX011613, ASCR, IMG_7214.
- `Videos CNMM/`: GX010664.MP4 (1,1 GB) y GX010665.MP4: los más largos; candidatos para el análisis de fatiga.
- 8 nadadores en total; de momento se trabaja con uno (crol).

## Memoria

Documento "TFM StrokeLab – Memoria (versión de revisión)" en claude.ai. Huecos marcados como [PENDIENTE].

## Siguientes pasos

1. `python diagnostico.py` y `python analizar.py <GX011615> --comparativa` en el portátil: velocidad real en CPU.
2. Validar el 3D (pesos reales de MotionBERT) frente al 2D en la vista lateral.
3. Analizar un vídeo largo (GX010664) para obtener el resultado de fatiga.
4. Volcar resultados en la memoria (Cap. 5) y actualizar Cap. 3 (YOLOv8n en CPU, MotionBERT, nuevas medidas).
