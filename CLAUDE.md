# StrokeLab · contexto para Claude

TFM de Diana Cruz (Máster en IA, Universidad Europea de Madrid). Entrega final: **15 de octubre de 2026**.
Sistema que analiza vídeo de natación y responde al entrenador: eficiencia de la brazada, **en qué momento
aparece la fatiga y por qué** (SHAP), y medidas de codos, hombros, caderas, rodillas y pies.

## Cómo se trabaja

- Todo se ejecuta **en local, en CPU**, en el portátil personal de Diana (Windows). No usar Colab salvo que lo pida.
- Programa principal: `python analizar.py "<vídeo>" --nadador "<nombre>"` (ver README para opciones).
- Pruebas antes de cada commit: `python tests/test_local.py`, `tests/test_sesion.py`, `tests/test_aaron.py` y `tests/test_movenet_recorte.py`.
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
- **Giro del fotograma para la pose 2D** (`--girar auto`): YOLO, entrenado con personas de pie, "inventaba" un cuerpo
  vertical bajo la cabeza de Aaron (GX011614). Se prueba el fotograma sin girar y girado ±90° en 8 tramos y se usa el
  giro que mejor detecta; las coordenadas se devuelven al fotograma original.
- **Vídeo anotado centrado en la fatiga** (petición de Diana): estado FRESCO/FATIGA, ciclo, frecuencia y barra temporal
  de anomalía por ciclo con umbral e inicio. Los ángulos van a los CSV (`--panel completo` para verlos en el vídeo).
- **Resultados en el portátil (CPU, 4 hilos)**: GX011614 (Aaron, crol, 5K, 46 s): YOLOv8n 6,6 FPS, YOLO11n 6,2,
  YOLOv8s 3,3 (detección 36-38 %, confianza 0,74-0,78); 7 ciclos válidos (Aaron en cuadro 17,5 s); MotionBERT 22 s.
  Pendiente: SR media 73 ciclos/min parece alta (contar a mano 10 s) y ángulos 3D de hombro/rodilla bajos (comparar con 2D).
- **Filtro de tronco girado**: se descartan fotogramas cuyo tronco se desvía > 45° de la dirección habitual del
  nadador (YOLO a veces lo pone de pie). En GX011614 quita el 11,5 % y la inclinación media pasa de 42° a 8,8°.
  Tras el filtro quedan 5 ciclos (Aaron analizable 12,7 s): un clip suelto no basta para fatiga.
- **Fatiga por sesión** (`sesion.py`): une las pasadas (clips) de un nadador en orden de grabación.
- **Conteo de brazadas por profundidad de la mano** (`medidas.detectar_ciclos`): con los keypoints reales de Aaron
  (tests/datos) se vio que YOLO copia el brazo visible en el oculto (muñecas I y D casi idénticas en vista lateral).
  Señal: profundidad de la mano más profunda respecto al eje del cuerpo, en 2D; ritmo = mediana de intervalos entre
  brazadas en 0,35-1,0 s; 1 ciclo = 2 brazadas. Validación: cuenta manual de Diana (s 30-40) = 54 ciclos/min;
  sistema = 50,0 (error 7 %), 8 ciclos válidos. Prueba: `tests/test_aaron.py`.
- Sospecha abierta en GX011614: ángulos 3D raros (rodilla 80°,
  hombro máx. 110°, alcance 0,47): posible confusión izquierda/derecha de MotionBERT bajo el agua. Comparar con 2D.
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
