"""Vídeo anotado: esqueleto (verde = fresco, rojo = fatiga) y panel con las medidas articulares."""
import cv2
import numpy as np

from .pose import SKELETON

ANCHO_SALIDA = 1280


def _txt(v):
    return ' --' if v is None or np.isnan(v) else f'{v:3.0f}'


def anotar(video, salida, kps, fr, ciclos, fps, nadador, formato='mp4'):
    """Escribe el vídeo anotado (máx. 1280 px de ancho). formato: 'mp4' (mp4v) o 'avi' (MJPG, se abre en todo)."""
    cap = cv2.VideoCapture(str(video))
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    sc = min(1.0, ANCHO_SALIDA / W)
    OW, OH = int(W * sc), int(H * sc)
    kv = kps * sc
    fourcc = cv2.VideoWriter_fourcc(*('MJPG' if formato == 'avi' else 'mp4v'))
    out = cv2.VideoWriter(str(salida), fourcc, fps, (OW, OH))
    T = len(kps)
    ciclo_de = np.full(T, -1)
    for i, r in ciclos.iterrows():
        a = int(r.t_inicio_s * fps)
        ciclo_de[a:a + int(r.duracion_s * fps)] = i
    tronco_ok = fr.codo_I.notna() | fr.codo_D.notna() | fr.cadera_I.notna() | fr.cadera_D.notna()
    for t in range(T):
        ok, f = cap.read()
        if not ok:
            break
        if sc < 1:
            f = cv2.resize(f, (OW, OH), interpolation=cv2.INTER_AREA)
        i = ciclo_de[t]
        fat = i >= 0 and 'estado' in ciclos and ciclos.estado.iloc[i] == 'fatigado'
        col = (0, 0, 255) if fat else (0, 200, 0)
        if tronco_ok.iloc[t]:                              # solo detecciones anatómicamente válidas
            for a, b in SKELETON:
                if not np.isnan(kv[t, [a, b]]).any():
                    cv2.line(f, tuple(kv[t, a].astype(int)), tuple(kv[t, b].astype(int)), col, 3)
        r_ = fr.iloc[t]
        lineas = [f'{nadador}   t = {t / fps:5.1f} s',
                  f'Codo    izq {_txt(r_.codo_I)}  dcho {_txt(r_.codo_D)} grados',
                  f'Hombro  izq {_txt(r_.hombro_I)}  dcho {_txt(r_.hombro_D)} grados',
                  f'Cadera  izq {_txt(r_.cadera_I)}  dcha {_txt(r_.cadera_D)} grados',
                  f'Rodilla izq {_txt(r_.rodilla_I)}  dcha {_txt(r_.rodilla_D)} grados']
        if i >= 0:
            c = ciclos.iloc[i]
            lineas.append(f'Ciclo {int(c.ciclo)} de {len(ciclos)}   SR {c.SR_ciclos_min:4.1f} ciclos/min')
            if 'anomalia' in ciclos:
                lineas.append(('FATIGA' if fat else 'FRESCO') + f'   (anomalia {c.anomalia:.2f})')
        cv2.rectangle(f, (10, 10), (470, 20 + 26 * len(lineas)), (0, 0, 0), -1)
        for k, s in enumerate(lineas):
            color = col if s.startswith(('FATIGA', 'FRESCO')) else (255, 255, 255)
            cv2.putText(f, s, (20, 36 + 26 * k), cv2.FONT_HERSHEY_SIMPLEX, 0.62, color, 2)
        out.write(f)
    cap.release()
    out.release()
