# StrokeLab · contexto para Claude

TFM de Diana Cruz (Máster en IA, Universidad Europea de Madrid). Entrega final: **15 de octubre de 2026**.
Sistema que analiza vídeo de natación y responde al entrenador: eficiencia de la brazada, **en qué momento
aparece la fatiga y por qué** (SHAP), y medidas de codos, hombros, caderas, rodillas y pies.

## Cómo se trabaja

- Todo se ejecuta **en local, en CPU**, en el portátil personal de Diana (Windows). No usar Colab salvo que lo pida.
- Programa principal: `python analizar.py "<vídeo>" --nadador "<nombre>"` (ver README para opciones).
- Pruebas antes de cada commit: `python tests/test_local.py`, `tests/test_sesion.py`, `tests/test_aaron.py`, `tests/test_movenet_recorte.py`,
  `tests/test_estilos.py`, `tests/test_lote.py`, `tests/test_frontal.py`, `tests/test_aaron_frontal.py`, `tests/test_simulador_estilo.py`, `tests/test_vista_auto.py`,
  `tests/test_estilo_reglas.py` y `tests/test_en_vivo.py`.
- **GPU (11 oct, GPU de la escuela)**: `--dispositivo auto` (defecto en analizar y lote) usa CUDA si PyTorch la ve; en el
  portátil sigue siendo CPU. Con GPU conviene `--imgsz 1280` (mejor detección del nadador pequeño). `diagnostico.py` dice si hay GPU.
- Todos los vídeos: `python lote.py --carpeta <videos> [--crear-lista]` (lista editable `lista_videos.csv`; reanudable).
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
  **Validación 3D (Aaron GX011614, 85 fotogramas, `validar_3d.py`)**: rodilla 2D 173° frente a 3D 107° (correlación
  ≈ 0); hombro 3D comprime el rango (82-107° frente a 50-153°); codo y cadera parecidos. MotionBERT reconstruye mal
  las piernas de un nadador horizontal bajo el agua. Decisión: en vista lateral los ángulos son 2D (`--vista lateral`,
  por defecto) y el 3D se guarda en columnas *_3d; en vistas frontales u oblicuas se usa el 3D (`--vista otra`).
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
- **Sesión de Aaron (opción A)**: GX011614 8-9 ciclos; GX011617 0 ciclos (detección 10 %, 7 s analizables);
  GX011618 1 ciclo (detección 20 %, 8,9 s). Los clips de GoPro de Aaron dan muy poca detección: la sesión no basta
  para concluir sobre fatiga. Siguiente: vídeo largo (opción B, GX010664 de Videos CNMM) o mejorar la detección.
- Emparejamiento de brazadas en ciclos tolera una brazada perdida (intervalo 1,5-2,6 T cuenta como 2 brazadas).
- **Filtro de plausibilidad anatómica** (`medidas.py`): tronco fuera de [0,5, 2] × mediana, segmentos de brazo y
  pierna implausibles, codos < 25°. Motivo: bajo el agua el modelo coloca a veces la cadera sobre el hombro.
- **Fatiga por ciclo de brazada**, comparando con el primer 30 % de ciclos del propio nadador; inicio = 3 ciclos
  seguidos por encima del percentil 95 de la fase fresca; contraste con PELT.
- **Ciclos por estilo** (`--estilo`, `medidas.ESTILOS`): crol y espalda 1 ciclo = 2 brazadas (0,35-1,0/1,2 s entre
  brazadas); mariposa y braza 1 ciclo = 1 brazada (0,7-2,0/2,4 s). Validado solo en crol real; resto con sintético.
- **Lote** (`lote.py`, 4 oct): sin vídeo anotado por defecto (`--con-video`) para ahorrar tiempo; sesión = mismo nombre
  en la lista (GoPro y móvil separados por defecto). Pendiente: clasificador de estilo (no implementado en local aún).
- **Lote de Aaron crol (5 oct)**: 5 clips, 118,8 s grabados, 35,8 s analizables (30 %), 17 ciclos. GoPro (lateral):
  GX011614 9 ciclos, GX011617 0 (sin 3 intervalos válidos: señal fragmentada), GX011618 1 → sesión 10 ciclos, sin fatiga.
  Móvil IMG_7207/7215 (1080x1920, 60 fps): tronco casi vertical en la imagen (78°/102°) y tronco de 60-100 px →
  NO es vista lateral (nada hacia la cámara o desde el borde): `vista otra` y fuera de las medidas (SR 80 no fiable).
  Cuello de botella: YOLO detecta al nadador en ~25 % de los fotogramas en que está en cuadro. Prueba: `probar_deteccion.py`
  (imgsz 640/1280 × conf 0,25/0,10); `--imgsz/--conf-det` en analizar y lote (`--rehacer-pose`).
- **Mínimos/máximos por ciclo robustos** (percentil 10/90, `medidas.bajo/alto`): con el mínimo puro, un fotograma
  malo daba rodillas de 12° en GX011614. Rodilla media por ciclo pasó de 107° a 149°.
- **Vista frontal** (`--vista frontal`, 5 oct; Diana necesita detectar al nadador de frente): brazadas por el recorrido
  de cada muñeca respecto al centro de hombros, en la dirección de máximo movimiento (PCA con cada brazo centrado),
  hacia abajo en la imagen, en anchos de hombros; alcance = recorrido de muñeca; sin inclinación ni velocidad; ángulos 3D.
  Sintético frontal (`tests/test_frontal.py`): SR 48,9 (verdad ~50), fatiga t = 47,5 s, SHAP: alcance, SR, asimetría.
  **Validación real (cuenta manual de Diana, 8 ciclos en cada clip entero)**: IMG_7207 80 manual vs 73,9 sistema
  (−7,6 %, 3 de 8 ciclos); IMG_7215 51,1 vs 55,2 (+8,2 %, 4 de 8). El ritmo se mide bien y distingue los dos ritmos;
  la cobertura es baja (38-50 % de los ciclos) por la detección. Prueba: `tests/test_aaron_frontal.py`.
- **Vista automática** (`--vista auto`, 11 oct, petición de Diana: sistema híbrido): `strokelab/vista.py` divide el vídeo en
  tramos de 60 s; frontal si >= 65 % de fotogramas con tronco a > 55° de la horizontal (reales: laterales <= 46 %,
  frontales >= 87 %); el cambio se ajusta al mejor fotograma. Cada tramo se analiza con su vista; la fatiga usa los ciclos
  de la vista con más ciclos (y `sesion.py` igual). 17/17 reales correctos (no independiente: umbral fijado con ellos);
  sintético 90 s lateral + 90 s frontal: cambio en 89,9 s. `lote.py --crear-lista` pone `auto` en los vídeos nuevos.
  Prueba: `tests/test_vista_auto.py`.
- **Carpetas de vídeos (11 oct)**: `outputs\videos\<Nadador>\<estilo>\vídeo` (libre = crol, dorso = espalda, pecho = braza,
  mariposa). `lote.py` recorre subcarpetas, guarda la ruta relativa en "archivo" y saca P1-P5 de la carpeta del nadador
  (Aaron P1, Alvaro P2, Lucia P3, Angel P4, Alvise P5) y el estilo de la subcarpeta. Alvise (nuevo, 8 vídeos) no tiene
  carpeta de estilo: estilo "?" hasta que Diana lo complete. Después movió todo a Alvise\libre (crol). Las carpetas mandan sobre una lista anterior en nadador y estilo. `reducir_video.py` conserva las carpetas.
- **Correcciones (11 oct, versión 2026-10-11)**: en vista lateral se descartan los fotogramas con el tronco a > 55° de la
  horizontal (`medidas.VERTICAL_LATERAL`). GX011610 (P1 mariposa) pasa de 7 ciclos (inclinación 84°, esqueletos de pie) a 0;
  GX011614 sin cambios. Braza P4: la frecuencia depende del t_min (0,7 s -> 80-84; 0,85 -> 41-75; 1,0 -> 40-55 ciclos/min):
  NO se cambia sin el conteo manual de Diana (pendiente: contar 10 s de GX011616).
- **Estilo por reglas biomecánicas** (`estilo.estimar_por_reglas`, 11 oct): el bosque aleatorio con vídeos reales aprendía
  al nadador (0 % con nadadores nuevos). Reglas: correlación de las manos (umbral lateral 0,65, frontal 0,20) -> brazos
  alternos/simultáneos (basta para contar ciclos: 2 o 1 brazadas); nariz respecto a hombros -> braza (< -0,05) / mariposa,
  espalda (< -0,30) / crol. Reales: familia 12/13, estilo 9/13 (umbrales fijados con ellos); sintéticos: familia 81 %.
  De frente no distingue mariposa de braza (lo dice). `analizar.py --estilo auto`; con estilo indicado, avisa si no coincide.
- **Tiempo real** (`en_vivo.py`, 11 oct): reproduce vídeo o cámara con pose en directo (o `--resultados` para reutilizar la
  pose) y panel CALIBRANDO/FRESCO/FATIGA con causas SHAP, estilo y vista. `fatiga.FatigaEnVivo`: base = primeros 10 ciclos,
  IF + p95 + 3 seguidos, SHAP por ciclo. Sintético 120 s (10+10 semillas, copia de brazos 0,5): 10/10 detectadas, 0/10 falsas.
- **Evaluación de la pose con nadadores anotados (12 oct, tras la entrega)**: Roboflow «Deep Dive Pose Technique» v6
  (CC BY 4.0): 405 imágenes reales GoPro subacuática lateral, 17 puntos COCO, 640x640 estiradas, 53 sin nadador; su
  partición aleatoria mezcla fotogramas de los mismos vídeos (fuga) -> `preparar_datos_pose.py` reparte por grabación
  (12 grabaciones, 4 pliegues equilibrados ~200/100/100). `evaluar_pose.py`: PCK@0,05/0,1/0,2 (escala max lado de la
  caja), OKS (sigmas COCO, área de la caja), detección y mAP de Ultralytics. YOLOv8n-Pose original en valid/test de
  Roboflow (conf 0,25): detección 8-16 % sin giro y 43-58 % con giro ±90° (valida el giro), PCK@0,1 12-14 %, OKS 0,12-0,14.
  `entrenar_pose.py` + `cluster/entrenar_pose.sbatch`: ajuste fino por pliegues y comparación original/ajustado.
  Pendiente: SwimXYZ (Freestyle_labels + vídeos part2) y fotogramas propios anotados como prueba final.
  **Resultado del ajuste fino (18 oct, clúster, 4 pliegues por grabación, ~97 nadadores y 13 imágenes vacías de prueba por
  pliegue, media)**: original sin giro: detección 15 %, OKS 0,05, PCK@0,1 4 %, PCK@0,2 7 %; original con giro: 47 %, 0,10, 9 %,
  15 %; ajustado sin giro: 78 %, 0,40, 37 %, 56 % (PCK@0,05 17 %), falsos positivos 3/13; ajustado con giro: 92 %, 0,38, 35 %,
  54 %, falsos positivos 10/13. El pliegue 0 (60 % PCK@0,1 en CPU) era el más fácil; el 3, el más difícil (26 %).
  Modelo para usar: `entrenar_pose.py --final` (405 imágenes, 60 épocas fijas, last.pt; los pliegues solo miden).
  `cluster/lote_ajustado.sbatch`: entrena el final si falta y pasa la lista con `lote.py --modelo` a ../resultados_ajustado
  (lote rehace la pose si el modelo_pose del resumen es otro). **Resultado en los vídeos propios (18 oct,
  `resultados_pose/comparacion_videos_original_ajustado.csv`)**: 17 vídeos del TFM (ambos a 640): analizable 132 -> 166 s
  (+26 %), ciclos 95 -> 109 (+15 %), pero desigual (GX011617 0->9, GX011618 1->11, IMG_7204 5->10; GX011609 5->0, IMG_7205,
  7213, 7217 -> 0). Frecuencia frente a la cuenta manual NO mejora: GX011614 54 manual: original 50,5 (-6 %), ajustado 73,0
  (+35 %); IMG_7207 80: 73,9 (-8 %) / 60,5 (-24 %); IMG_7215 51,1: 55,2 (+8 %) / 54,5 (+7 %). Vídeo largo GX010731 (P5):
  130 -> 254 s, 19 -> 62 ciclos, pero el inicio de fatiga de 748 s (original, 1280) NO se reproduce: sin fatiga. La sesión P5
  gopro (5 clips de días distintos, orden por nombre) da inicio a 91,5 s de GX010731: probable cambio de condiciones entre
  clips, no fatiga. ASCR y GX011613 son el mismo vídeo (keypoints idénticos).
  Causa del +35 % en GX011614 con el ajustado: picos dobles en la señal de la mano (T = 0,43 s, intervalos de 0,23-0,4 s;
  manual 18 brazadas en 30-40 s = 0,55 s). Suavizar la señal 0,15 s: GX011614 48,7 (-10 %), IMG_7215 +5 %, IMG_7207 -26 %
  (2 ciclos). Con el original el mismo suavizado empeora. NO se cambia: 3 cuentas manuales no bastan para calibrar
  (pendiente: más cuentas manuales de Diana). `cluster/entrenar_pose_grandes.sbatch`: mismos pliegues con YOLOv8s y v8m
  (`entrenar_pose.py --base`). **YOLOv8m (18 oct, media 4 pliegues)**: original sin giro 40 %, OKS 0,17, PCK@0,1 15 %,
  PCK@0,2 23 %; original con giro 68 %, 0,22, 19 %, 30 %; ajustado sin giro 69 %, 0,35, 33 %, 50 % (FP 2,5/13); ajustado con
  giro 86 %, 0,34, 33 %, 49 % (FP 7,75/13). El m original es mucho mejor que el n original, pero ajustado NO supera al n
  ajustado (0,40 / 37 %): con ~200 imágenes de entrenamiento el modelo grande no aprovecha su tamaño. **YOLOv8s**: original
  sin giro 21 %, OKS 0,07, PCK@0,1 5 %; con giro 58 %, 0,14, 12 %, 20 %; ajustado sin giro 76 %, 0,37, 34 %, 54 % (FP 3,5/13);
  con giro 95 %, 0,35, 31 %, 51 % (FP 12,75/13). Conclusión: tras el ajuste n ≈ s ≈ m (OKS 0,35-0,40); se mantiene YOLOv8n.
  Con el modelo ajustado las reglas posteriores fallan (calibradas con la pose del original): video2 (YouTube, cámara en el
  fondo) sale lateral en vez de frontal (48 % de troncos descartados, 3 ciclos frente a 13) y estilo mariposa; Thorpe sale
  mariposa. Decisión: el sistema del TFM sigue con el modelo original; recalibrar vista/ciclos/estilo es trabajo futuro.
  **SwimXYZ** (`convertir_swimxyz.py`): etiquetas por secuencia en <vista>/<agua>/<luz>/<velocidad>/<posición>/body25/2D_cam.txt
  («Nombre.x;Nombre.y;Nombre.z», coma decimal, px); la carpeta COCO trae 18 puntos (OpenPose) con cabecera de BODY25: se usa
  body25 por nombre. Hacen falta los vídeos (misma ruta relativa). Solo entrenamiento: `preparar_datos_pose.py
  --solo-entrenamiento`. La y de SwimXYZ va desde abajo (comprobado con revisar_*.jpg): usar --y-desde-abajo. Vista Front = cámara fuera del agua al fondo de la piscina, nadador ~100 px de 1920: se recorta un cuadrado de 3x el nadador. Vídeos .webm de Zenodo 8402009 (Front y Aerial, 41,7 GB) bajados en parte con descargar_swimxyz.py (48 Front -> 777 imágenes). **Resultado con SwimXYZ (19 oct, mismos pliegues de prueba
  reales, 777 sintéticas solo en entrenamiento, YOLOv8n)**: sin giro detección 76 % (antes 78), OKS 0,392 (0,397), PCK@0,05
  18,6 % (17,2), PCK@0,1 38,3 % (37,0), PCK@0,2 54 % (56), falsos positivos 6,75/13 (3). Sin mejora clara en la prueba
  (lateral bajo el agua; SwimXYZ Front es fuera del agua) y más falsos positivos (las sintéticas siempre tienen nadador).
  Pliegue 3 (el difícil): detección 60 -> 84 %, PCK@0,1 26,1 -> 26,9 %. Medir la ventaja en vista frontal exige
  imágenes frontales reales anotadas (pendiente).
- **Versión del análisis** (`strokelab.VERSION_ANALISIS`): lote.py rehace (reutilizando la pose) los vídeos analizados
  con otra versión. Motivo: el 2º zip de Diana (4 oct 23:05) traía resultados del código viejo porque el lote los saltó.
  Subir la fecha cada vez que cambien medidas, ciclos o fatiga.
- `informe_nadador.py <resultados> --nadador X --estilo Y`: tablas y figuras por clip y por variable (solo vista lateral).
- Variables redundantes fuera del modelo (v = SR·DPS; potencia ∝ v³).
- El 99,99 % de accuracy de versiones antiguas era fuga de datos; la clasificación de estilo usa GroupKFold por vídeo.

## Datos (Google Drive de Diana)

- `Videos_TFM/Nadador A/`: GX011615.MP4 (34 s, una pasada, sirve para validar pero no para fatiga), GX011613, ASCR, IMG_7214.
- `Videos CNMM/`: GX010664.MP4 (1,1 GB) y GX010665.MP4: los más largos; candidatos para el análisis de fatiga.
- 8 nadadores en total; de momento se trabaja con uno (crol).

## Memoria

- Borrador vivo: documento "TFM StrokeLab – Memoria (versión de revisión)" en claude.ai
  (https://claude.ai/code/artifact/887425c4-4432-4c90-9862-b247bfdd8fe8).
- Entrega final: plantilla de la escuela `memoria/Plantilla_memoria_TFM.docx`, rellenada por
  `memoria/generar_memoria.py` -> `memoria/TFM_StrokeLab_borrador.docx`. Base antigua (sept., con resultados no
  válidos: 5 nadadores con potencia, 99,9 %, LSTM): `memoria/TFM_STROKELAB_ACTUALIZADO_base_sept.docx`.
- **Versión revisada (7 oct, comentarios del director)**: 54 págs. Título nuevo («StrokeLab: desarrollo de un sistema de
  análisis biomecánico explicable…»); registro científico; participante P1 (no nombres); «datos sintéticos»; marco teórico
  de ML/visión (CNN, pose, OKS/PCK/mAP, Isolation Forest, PELT, Random Forest, SHAP, PCA) y justificación de no usar
  modelo propio y de no calcular mAP/PCK/OKS (sin anotaciones); 19 ecuaciones OMML numeradas con índice; citas IEEE
  numeradas con enlace; Gantt; tablas sin partir; Cap. 7 en prosa. `generar_memoria.py` hace 2 pasadas y llama a
  `actualizar_indices.py` (LibreOffice + libreoffice-math) -> `TFM_StrokeLab_final.docx`. Pruebas: + test_simulador_estilo.
- **Versión ampliada (8 oct, 71 págs.)**: conjunto real completo (17 secuencias, P1-P4, 4 estilos, 394 s, 146 s analizables,
  100 ciclos), perfiles por participante, fatiga en 3 sesiones (sin fatiga, sin falsas alarmas), estilo con vídeos reales
  (45,5 % por vídeo dejando un vídeo fuera; 9,1 % dejando un participante fuera; base 36,4 %), sensibilidad y robustez
  (datos sintéticos, presentados como tales), ética, arquitectura, Anexos D-F. Los datos sintéticos NUNCA se presentan como reales.
  Pendiente: validar a mano la frecuencia de braza de P4 (79,5 parece sobrestimada) y el consentimiento de los nadadores.
- **Memoria automática (11 oct)**: los resultados reales (tablas, cifras del resumen/abstract, cap. 1, 4.6, 5, 6 y Anexo D,
  figuras real_*) salen de `memoria/datos_reales` vía `memoria/resultados_reales.py`. Para actualizar con un análisis nuevo:
  `python memoria/importar_resultados.py <para_claude.zip>` y `python memoria/generar_memoria.py`. Base actual: 17 vídeos
  reanalizados en local con el código 2026-10-11 (imgsz 640); pendiente el zip del clúster (imgsz 1280, + P5 y vídeo de 36 min).
- Datos de la portada pendientes: apellidos de Diana, director/a, horas y presupuesto, equipo, agradecimientos,
  conclusiones personales, fechas de la fase 1, comparativa MoveNet/MediaPipe en CPU y resultado de fatiga real.

## Siguientes pasos

1. Nuevos vídeos de Diana (más largos) para el resultado de fatiga real; la sesión GX011614/17/18 da ~10 ciclos.
2. MoveNet y MediaPipe en la CPU del portátil (`--comparativa`) para completar la Tabla 3.1.
3. Rellenar los [PENDIENTE] de la memoria final y regenerar el .docx.
