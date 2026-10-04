"""Vídeo anotado.

Panel 'fatiga' (por defecto): estado FRESCO / FATIGA, ciclo y frecuencia, y una barra temporal con la anomalía de
cada ciclo, el umbral y el inicio de la fatiga. Panel 'completo': además los ángulos articulares.
"""
import cv2
import numpy as np

from .pose import SKELETON

ANCHO_SALIDA = 1280
VERDE, ROJO, BLANCO, GRIS, NEGRO = (60, 200, 60), (40, 40, 230), (255, 255, 255), (150, 150, 150), (0, 0, 0)
FUENTE = cv2.FONT_HERSHEY_SIMPLEX


def _txt(v):
    return ' --' if v is None or np.isnan(v) else f'{v:3.0f}'


def _caja(f, x0, y0, x1, y1, alfa=0.6):
    """Rectángulo negro semitransparente."""
    sub = f[y0:y1, x0:x1]
    f[y0:y1, x0:x1] = (sub * (1 - alfa)).astype(f.dtype)


def _barra_fatiga(f, ciclos, res, t, dur_total):
    """Barra inferior: un bloque por ciclo cuya altura es su anomalía (verde -> rojo), umbral, inicio y cursor."""
    h, w = f.shape[:2]
    x0, x1, y1 = 20, w - 20, h - 20
    alto = 70
    y0 = y1 - alto
    _caja(f, x0 - 10, y0 - 34, x1 + 10, y1 + 10)
    cv2.putText(f, 'Fatiga por ciclo de brazada', (x0, y0 - 12), FUENTE, 0.55, BLANCO, 1, cv2.LINE_AA)
    X = lambda s: int(x0 + (x1 - x0) * s / dur_total)
    anom = ciclos.anomalia.to_numpy()
    lo, hi = min(anom.min(), res['umbral']), max(anom.max(), res['umbral'])
    Y = lambda a: int(y1 - (a - lo) / (hi - lo + 1e-9) * (alto - 6))
    for _, c in ciclos.iterrows():
        mezcla = np.clip((c.anomalia - lo) / (res['umbral'] - lo + 1e-9), 0, 1.5) / 1.5
        col = tuple(int(v) for v in (np.array(VERDE) * (1 - mezcla) + np.array(ROJO) * mezcla))
        cv2.rectangle(f, (X(c.t_inicio_s), Y(c.anomalia)), (max(X(c.t_inicio_s + c.duracion_s) - 1, X(c.t_inicio_s) + 1), y1), col, -1)
    yu = Y(res['umbral'])
    for xx in range(x0, x1, 12):                           # umbral discontinuo
        cv2.line(f, (xx, yu), (min(xx + 6, x1), yu), BLANCO, 1)
    cv2.putText(f, 'umbral', (x1 - 60, yu - 4), FUENTE, 0.45, BLANCO, 1, cv2.LINE_AA)
    if res.get('t_inicio') is not None:
        xi = X(res['t_inicio'])
        cv2.line(f, (xi, y0 - 4), (xi, y1), ROJO, 3)
        cv2.putText(f, f'inicio fatiga {res["t_inicio"]:.1f} s', (min(xi + 6, x1 - 170), y0 + 14), FUENTE, 0.5, ROJO, 2, cv2.LINE_AA)
    xc = X(t)
    cv2.line(f, (xc, y0 - 4), (xc, y1 + 4), BLANCO, 2)


def anotar(video, salida, kps, fr, ciclos, fps, nadador, formato='mp4', res=None, panel='fatiga'):
    """Escribe el vídeo anotado (máx. 1280 px de ancho). formato: 'mp4' (mp4v) o 'avi' (MJPG, se abre en todo)."""
    res = res or {}
    cap = cv2.VideoCapture(str(video))
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    sc = min(1.0, ANCHO_SALIDA / W)
    OW, OH = int(W * sc), int(H * sc)
    kv = kps * sc
    fourcc = cv2.VideoWriter_fourcc(*('MJPG' if formato == 'avi' else 'mp4v'))
    out = cv2.VideoWriter(str(salida), fourcc, fps, (OW, OH))
    T = len(kps)
    dur_total = T / fps
    ciclo_de = np.full(T, -1)
    for i, r in ciclos.iterrows():
        a = int(r.t_inicio_s * fps)
        ciclo_de[a:a + int(r.duracion_s * fps)] = i
    hay_fatiga = 'anomalia' in ciclos and 'umbral' in res
    valido = (fr.codo_I.notna() | fr.codo_D.notna() | fr.cadera_I.notna() | fr.cadera_D.notna()).to_numpy()
    for t in range(T):
        ok, f = cap.read()
        if not ok:
            break
        if sc < 1:
            f = cv2.resize(f, (OW, OH), interpolation=cv2.INTER_AREA)
        i = ciclo_de[t]
        fat = hay_fatiga and res.get('inicio') is not None and t / fps >= res['t_inicio']
        col = ROJO if fat else VERDE
        if valido[t]:                                      # solo detecciones anatómicamente válidas
            for a, b in SKELETON:
                if not np.isnan(kv[t, [a, b]]).any():
                    cv2.line(f, tuple(kv[t, a].astype(int)), tuple(kv[t, b].astype(int)), col, 3, cv2.LINE_AA)

        lineas = [(f'{nadador}   t = {t / fps:5.1f} s', BLANCO, 0.6, 1)]
        if i >= 0:
            c = ciclos.iloc[i]
            lineas.append((f'Ciclo {int(c.ciclo)} de {len(ciclos)}   {c.SR_ciclos_min:4.1f} ciclos/min', BLANCO, 0.6, 1))
        if hay_fatiga:
            lineas.append(('FATIGA' if fat else 'FRESCO', col, 1.1, 3))
        else:
            lineas.append((f'Fatiga no evaluable: {len(ciclos)} ciclos validos', GRIS, 0.55, 1))
        if panel == 'completo':
            r_ = fr.iloc[t]
            lineas += [(f'Codo    izq {_txt(r_.codo_I)}  dcho {_txt(r_.codo_D)}', BLANCO, 0.55, 1),
                       (f'Hombro  izq {_txt(r_.hombro_I)}  dcho {_txt(r_.hombro_D)}', BLANCO, 0.55, 1),
                       (f'Cadera  izq {_txt(r_.cadera_I)}  dcha {_txt(r_.cadera_D)}', BLANCO, 0.55, 1),
                       (f'Rodilla izq {_txt(r_.rodilla_I)}  dcha {_txt(r_.rodilla_D)}', BLANCO, 0.55, 1)]
        alto = 14 + sum(int(34 * e) + 6 for _, _, e, _ in lineas)
        _caja(f, 10, 10, 430, 10 + alto)
        y = 18
        for s, color, escala, grosor in lineas:
            y += int(34 * escala)
            cv2.putText(f, s, (22, y), FUENTE, escala, color, grosor, cv2.LINE_AA)
            y += 6
        if hay_fatiga:
            _barra_fatiga(f, ciclos, res, t / fps, dur_total)
        out.write(f)
    cap.release()
    out.release()
