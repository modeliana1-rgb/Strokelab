"""Vertical 1 · Estimación de pose 2D (formato COCO-17) en CPU.

Modelos disponibles:
  - 'yolov8n-pose', 'yolo11n-pose', 'yolov8s-pose', ... (Ultralytics, PyTorch)   <- recomendado
  - 'movenet_lightning', 'movenet_thunder' (TensorFlow Hub)
  - 'mediapipe' (BlazePose, 33 puntos mapeados a COCO-17)

Todas las funciones devuelven coordenadas en PÍXELES DEL VÍDEO ORIGINAL.
"""
import time

import cv2
import numpy as np

# Índices COCO-17
NOSE, LSH, RSH, LEL, REL, LWR, RWR, LHIP, RHIP, LKN, RKN, LAN, RAN = 0, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16
SKELETON = [(5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (5, 11), (6, 12), (11, 12),
            (11, 13), (13, 15), (12, 14), (14, 16), (0, 5), (0, 6)]

# MediaPipe BlazePose (33) -> COCO-17
MP_A_COCO = [0, 2, 5, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]

MOVENET_URLS = {'lightning': ['https://tfhub.dev/google/movenet/singlepose/lightning/4',
                              'https://www.kaggle.com/models/google/movenet/TensorFlow2/singlepose-lightning/4'],
                'thunder': ['https://tfhub.dev/google/movenet/singlepose/thunder/4',
                            'https://www.kaggle.com/models/google/movenet/TensorFlow2/singlepose-thunder/4']}
MOVENET_TAM = {'lightning': 192, 'thunder': 256}

MP_MODELO_URL = ('https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/'
                 'float16/latest/pose_landmarker_full.task')

MAX_LADO = 1920   # los fotogramas 4K/5K se reducen a este lado mayor antes del modelo (los modelos usan 192-640 px)


def reducir(frame, max_lado=MAX_LADO):
    """Reduce el fotograma si es muy grande. Devuelve (fotograma, factor) con coords_originales = coords / factor."""
    h, w = frame.shape[:2]
    f = min(1.0, max_lado / max(h, w))
    if f < 1.0:
        frame = cv2.resize(frame, (int(round(w * f)), int(round(h * f))), interpolation=cv2.INTER_AREA)
    return frame, f


# ---------------------------------------------------------------- Giro del fotograma
# Los modelos de pose se entrenaron sobre todo con personas de pie. Con un nadador en horizontal tienden a
# "inventar" un cuerpo vertical. Girando el fotograma 90° el nadador queda de pie para el modelo; después se
# deshace el giro en las coordenadas.
def girar(frame, rot):
    if rot == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    if rot == -90:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return frame


def desgirar(xy, rot, ancho, alto):
    """Coordenadas del fotograma girado -> fotograma original (ancho x alto antes de girar)."""
    if rot == 90:
        return np.c_[xy[:, 1], alto - 1 - xy[:, 0]]
    if rot == -90:
        return np.c_[ancho - 1 - xy[:, 1], xy[:, 0]]
    return xy


# ---------------------------------------------------------------- MoveNet
def recorte_cuadrado(frame, cx, cy, lado):
    """Cuadrado de 'lado' px centrado en (cx, cy); lo que cae fuera del vídeo queda en negro."""
    alto, ancho = frame.shape[:2]
    lado = int(round(lado))
    x0, y0 = int(round(cx - lado / 2)), int(round(cy - lado / 2))
    lienzo = np.zeros((lado, lado, 3), frame.dtype)
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(ancho, x0 + lado), min(alto, y0 + lado)
    if xb > xa and yb > ya:
        lienzo[ya - y0:yb - y0, xa - x0:xb - x0] = frame[ya:yb, xa:xb]
    return lienzo, x0, y0, lado


class SeguidorMoveNet:
    """MoveNet + recorte cuadrado que sigue al nadador. infer(rgb tam x tam) -> (17, 3) [y, x, score] normalizados.

    Al ser el recorte cuadrado no hay relleno que deshacer: x = x0 + x_norm * lado.
    """

    def __init__(self, infer, tam, ancho, alto, umbral=0.2):
        self.infer, self.tam, self.ancho, self.alto, self.umbral = infer, tam, ancho, alto, umbral
        self.region = None

    def __call__(self, frame):
        lado_max = max(self.ancho, self.alto)
        cx, cy, lado = self.region or (self.ancho / 2, self.alto / 2, lado_max)
        img, x0, y0, lado = recorte_cuadrado(frame, cx, cy, lado)
        rgb = cv2.cvtColor(cv2.resize(img, (self.tam, self.tam), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
        out = self.infer(rgb)
        xy = np.c_[x0 + out[:, 1] * lado, y0 + out[:, 0] * lado]
        sc = out[:, 2]
        ok = sc > self.umbral
        if ok.sum() >= 5:                                   # siguiente recorte: caja del cuerpo x 1.6
            (xa, ya), (xb, yb) = xy[ok].min(0), xy[ok].max(0)
            self.region = ((xa + xb) / 2, (ya + yb) / 2,
                           float(np.clip(1.6 * max(xb - xa, yb - ya), 0.25 * lado_max, lado_max)))
        else:
            self.region = None                              # perdido: vuelve a buscar en todo el fotograma
        return xy, sc


def cargar_movenet(variante):
    import tensorflow as tf
    try:
        import tensorflow_hub as hub
    except ModuleNotFoundError as e:
        if 'pkg_resources' in str(e):
            raise ModuleNotFoundError('tensorflow_hub necesita pkg_resources: ejecuta  pip install --user "setuptools<81"') from e
        raise
    ultimo = None
    for url in MOVENET_URLS[variante]:
        try:
            mod = hub.load(url).signatures['serving_default']
            return (lambda rgb: mod(tf.constant(rgb[None].astype(np.int32)))['output_0'].numpy()[0, 0]), MOVENET_TAM[variante]
        except Exception as e:
            ultimo = e
    raise RuntimeError(f'No se pudo cargar MoveNet {variante}: {ultimo}')


# ---------------------------------------------------------------- Estimadores
class Estimador:
    """Interfaz común: est(frame_bgr) -> (xy (17,2) px del fotograma recibido, conf (17,)). est.reiniciar() entre tramos."""

    def __init__(self, modelo, ancho, alto):
        self.modelo = modelo
        self.prev_c = None
        if modelo.startswith('movenet'):
            infer, tam = cargar_movenet(modelo.split('_')[1])
            self.seg = SeguidorMoveNet(infer, tam, ancho, alto)
            self.tipo = 'movenet'
        elif modelo == 'mediapipe':
            self._iniciar_mediapipe()
            self.tipo = 'mediapipe'
        else:
            from ultralytics import YOLO
            self.yolo = YOLO(modelo if modelo.endswith('.pt') else modelo + '.pt')
            self.tipo = 'yolo'

    def _iniciar_mediapipe(self):
        import mediapipe as mp
        self.mp_mod = mp
        if hasattr(mp, 'solutions'):                       # MediaPipe < 1.0
            self.mp = mp.solutions.pose.Pose(static_image_mode=False, model_complexity=1,
                                             min_detection_confidence=0.3, min_tracking_confidence=0.3)
            self.mp_tasks = False
            return
        # MediaPipe >= 1.0: API de Tasks (PoseLandmarker) con el modelo descargado una vez
        import urllib.request
        from pathlib import Path
        from mediapipe.tasks import python as mpt
        from mediapipe.tasks.python import vision
        ruta = Path('modelos') / 'mediapipe' / 'pose_landmarker_full.task'
        if not ruta.exists():
            ruta.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(MP_MODELO_URL, ruta)
        opciones = vision.PoseLandmarkerOptions(
            base_options=mpt.BaseOptions(model_asset_path=str(ruta)), running_mode=vision.RunningMode.VIDEO,
            num_poses=1, min_pose_detection_confidence=0.3, min_tracking_confidence=0.3)
        self.mp = vision.PoseLandmarker.create_from_options(opciones)
        self.mp_tasks, self.mp_t = True, 0

    def reiniciar(self):
        self.prev_c = None
        if self.tipo == 'movenet':
            self.seg.region = None

    def __call__(self, frame):
        if self.tipo == 'movenet':
            return self.seg(frame)
        if self.tipo == 'mediapipe':
            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            if self.mp_tasks:
                self.mp_t += 33                            # marca de tiempo creciente (ms) que exige el modo VIDEO
                r = self.mp.detect_for_video(self.mp_mod.Image(image_format=self.mp_mod.ImageFormat.SRGB,
                                                               data=np.ascontiguousarray(rgb)), self.mp_t)
                if not r.pose_landmarks:
                    return np.full((17, 2), np.nan), np.zeros(17)
                lm = r.pose_landmarks[0]
            else:
                r = self.mp.process(rgb)
                if r.pose_landmarks is None:
                    return np.full((17, 2), np.nan), np.zeros(17)
                lm = r.pose_landmarks.landmark
            xy = np.array([[lm[i].x * w, lm[i].y * h] for i in MP_A_COCO])
            return xy, np.array([lm[i].visibility for i in MP_A_COCO])
        r = self.yolo(frame, verbose=False, device='cpu')[0]
        if r.keypoints is None or r.keypoints.conf is None or len(r.boxes) == 0:
            return np.full((17, 2), np.nan), np.zeros(17)
        xy = r.keypoints.xy.cpu().numpy()
        cf = r.keypoints.conf.cpu().numpy()
        cajas = r.boxes.xywh.cpu().numpy()
        centros = cajas[:, :2]
        if self.prev_c is None:      # primera vez: la detección más grande y segura
            i = int((r.boxes.conf.cpu().numpy() * cajas[:, 2:].prod(1)).argmax())
        else:                        # después: la más cercana a la posición anterior del nadador
            i = int(np.linalg.norm(centros - self.prev_c, axis=1).argmin())
        self.prev_c = centros[i]
        return xy[i], cf[i]


class EstimadorGirado:
    """Estimador que trabaja sobre el fotograma girado 'rot' grados y devuelve coordenadas del original."""

    def __init__(self, modelo, ancho, alto, rot=0):
        self.rot, self.ancho, self.alto = rot, ancho, alto
        self.est = Estimador(modelo, *((alto, ancho) if rot else (ancho, alto)))

    def reiniciar(self):
        self.est.reiniciar()

    def __call__(self, frame):
        xy, cf = self.est(girar(frame, self.rot))
        return desgirar(xy, self.rot, frame.shape[1], frame.shape[0]), cf


def extraer_keypoints(video, modelo='yolov8n-pose', cada=1, progreso=True, rot=0):
    """Procesa el vídeo completo. Con cada=2 analiza un fotograma de cada dos (el resto se interpola después).

    Devuelve kps (T,17,2) en px originales (NaN donde no hay detección), conf (T,17), fps, ancho, alto.
    """
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise FileNotFoundError(f'No se puede abrir el vídeo: {video}')
    fps = cap.get(cv2.CAP_PROP_FPS)
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    f_red = min(1.0, MAX_LADO / max(W, H))
    est = EstimadorGirado(modelo, int(round(W * f_red)), int(round(H * f_red)), rot)
    kps = np.full((N, 17, 2), np.nan)
    conf = np.zeros((N, 17))
    t0 = time.time()
    t = -1
    for t in range(N):
        ok = cap.grab()                      # avanza sin decodificar; solo se decodifica lo que se analiza
        if not ok:
            t -= 1
            break
        if t % cada:
            continue
        _, f = cap.retrieve()
        f, fr = reducir(f)
        xy, cf = est(f)
        kps[t], conf[t] = xy / fr, cf
        if progreso and t % 300 == 0:
            print(f'  fotograma {t}/{N}  ({(t + 1) / max(time.time() - t0, 1e-6):.1f} fotogramas/s)')
    cap.release()
    T = t + 1
    kps, conf = kps[:T], conf[:T]
    kps[conf == 0] = np.nan
    return kps, conf, fps, W, H


def leer_tramos(video, n_tramos=15, largo=10):
    """Tramos de 'largo' fotogramas seguidos repartidos por todo el vídeo, reducidos a 1280 px."""
    cap = cv2.VideoCapture(str(video))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    tramos = []
    for i in np.linspace(0, max(total - largo, 0), n_tramos).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        tramo = []
        for _ in range(largo):
            ok, f = cap.read()
            if not ok:
                break
            tramo.append(reducir(f, 1280)[0])
        if tramo:
            tramos.append(tramo)
    cap.release()
    return tramos


def _puntuar(est, tramos, conf_min=0.30):
    """Ejecuta el estimador sobre los tramos: (fps, tasa de detección %, confianza media)."""
    est(tramos[0][0])                                      # calentamiento
    confs, t0, n = [], time.time(), 0
    for tramo in tramos:
        est.reiniciar()
        for f in tramo:
            confs.append(est(f)[1])
            n += 1
    fps = n / (time.time() - t0)
    c = np.array(confs)
    det = (c > conf_min).sum(1) >= 5
    return fps, float(100 * det.mean()), float(c[det].mean()) if det.any() else 0.0


def elegir_rotacion(video, modelo):
    """Prueba el fotograma sin girar y girado ±90° en 8 tramos del vídeo; elige el que mejor detecta."""
    tramos = leer_tramos(video, n_tramos=8, largo=5)
    h, w = tramos[0][0].shape[:2]
    filas = []
    for rot in (0, 90, -90):
        _, det, conf = _puntuar(EstimadorGirado(modelo, w, h, rot), tramos)
        filas.append((rot, det, conf, det / 100 * conf))
        print(f'   giro {rot:+4d}°: detección {det:5.1f} %  confianza {conf:.3f}  puntuación {det / 100 * conf:.3f}')
    return max(filas, key=lambda f: f[3])[0]


def comparar_modelos(video, modelos, conf_min=0.30, rot=0):
    """Comparativa en CPU: FPS, % de fotogramas con >= 5 articulaciones fiables, confianza media."""
    import pandas as pd
    tramos = leer_tramos(video)
    h, w = tramos[0][0].shape[:2]
    filas = []
    for m in modelos:
        try:
            fps, det, conf = _puntuar(EstimadorGirado(m, w, h, rot), tramos, conf_min)
            filas.append(dict(modelo=m, giro=rot, fps_cpu=round(fps, 1), tasa_deteccion=round(det, 1),
                              conf_media=round(conf, 3)))
            print('  ', filas[-1])
        except Exception as e:
            print(f'   omitido {m}: {type(e).__name__}: {str(e)[:120]}')
    tabla = pd.DataFrame(filas)
    if len(tabla):
        tabla['puntuacion'] = (tabla.tasa_deteccion / 100 * tabla.conf_media).round(3)
    return tabla
