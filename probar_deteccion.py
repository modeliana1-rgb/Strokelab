"""StrokeLab · ¿detecta YOLO mejor al nadador con más resolución de entrada o menos confianza mínima?

Prueba 4 ajustes de YOLOv8n-Pose sobre fotogramas del tramo en el que el nadador está en cuadro y mide, en CPU,
la velocidad, el % de fotogramas con el nadador detectado (>= 5 articulaciones fiables) y la confianza media.

Uso:  python probar_deteccion.py "C:\\Users\\user\\StrokeLab\\videos\\GX011617.MP4" --desde 10 --hasta 29
"""
import argparse
import os
import sys

os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')

import cv2
import numpy as np
import pandas as pd

from strokelab import pose

AJUSTES = [(640, 0.25), (640, 0.10), (1280, 0.25), (1280, 0.10)]


def fotogramas(video, desde, hasta, n):
    cap = cv2.VideoCapture(str(video))
    fps, total = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    a, b = int(desde * fps), min(total - 1, int(hasta * fps) if hasta else total - 1)
    tramos = []
    for i in np.linspace(a, max(a, b - 5), n // 5).astype(int):     # tramos de 5 fotogramas seguidos
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        tramo = [pose.reducir(f)[0] for ok, f in (cap.read() for _ in range(5)) if ok]
        if tramo:
            tramos.append(tramo)
    cap.release()
    return tramos


def main(argv=None):
    ap = argparse.ArgumentParser(description='Compara ajustes de YOLO en el tramo con nadador.')
    ap.add_argument('video')
    ap.add_argument('--desde', type=float, default=0, help='segundo en que el nadador entra en cuadro')
    ap.add_argument('--hasta', type=float, help='segundo en que sale')
    ap.add_argument('--modelo', default='yolov8n-pose')
    ap.add_argument('--n', type=int, default=60, help='fotogramas a probar')
    a = ap.parse_args(argv)

    tramos = fotogramas(a.video, a.desde, a.hasta, a.n)
    h, w = tramos[0][0].shape[:2]
    filas = []
    for imgsz, conf in AJUSTES:
        pose.YOLO_IMGSZ, pose.YOLO_CONF = imgsz, conf
        fps, det, cm = pose._puntuar(pose.EstimadorGirado(a.modelo, w, h, 0), tramos)
        filas.append(dict(imgsz=imgsz, conf_det=conf, fps_cpu=round(fps, 1), deteccion_pct=round(det, 1), conf_media=round(cm, 3)))
        print('  ', filas[-1])
    tabla = pd.DataFrame(filas)
    tabla['puntuacion'] = (tabla.deteccion_pct / 100 * tabla.conf_media).round(3)
    print('\n' + tabla.to_string(index=False))
    mejor = tabla.loc[tabla.puntuacion.idxmax()]
    print(f'\nMejor: --imgsz {int(mejor.imgsz)} --conf-det {mejor.conf_det}  '
          f'(detección {mejor.deteccion_pct} % frente a {tabla.deteccion_pct.iloc[0]} % con los ajustes por defecto)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
