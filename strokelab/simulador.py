"""Nadador SIMULADO (ficticio) para demostrar y probar el sistema cuando se conoce la verdad.

Genera los 17 puntos COCO de un nadador en vista lateral (cámara fija de lado que cubre la piscina) o frontal
(cámara delante del nadador), en cualquiera de los 4 estilos, con fatiga programada: a partir de t_fatiga sube la
frecuencia de ciclo, baja la velocidad y la distancia por ciclo, se acorta el alcance, se flexiona más el codo, se
hunde la cadera y aparece asimetría. Devuelve también la verdad (frecuencia, velocidad y fatiga en cada instante)
para medir el error del sistema. Las longitudes del cuerpo están en metros y se pasan a píxeles con px_por_m.

No son datos reales: sirve para validar el método y para la demostración de la memoria (caso ficticio).
"""
import numpy as np
import pandas as pd

ESTILOS = ['crol', 'espalda', 'mariposa', 'braza']
# periodo del ciclo (s) fresco -> fatigado, velocidad (m/s) fresco -> fatigado
PARAMS = {
    'crol': dict(T=(1.30, 1.10), v=(1.55, 1.30)),
    'espalda': dict(T=(1.40, 1.20), v=(1.40, 1.20)),
    'mariposa': dict(T=(1.20, 1.05), v=(1.45, 1.20)),
    'braza': dict(T=(1.50, 1.30), v=(1.20, 1.00)),
}
BRAZO, ANTEBRAZO, MUSLO, PIERNA, TRONCO = 0.32, 0.30, 0.46, 0.44, 0.50


def _codo(a, c, l1, l2, flex):
    """Articulación intermedia (codo o rodilla) por cinemática inversa de 2 segmentos, doblada hacia 'flex'."""
    d = c - a
    dist = np.linalg.norm(d, axis=1, keepdims=True)
    dist = np.clip(dist, 1e-6, l1 + l2 - 1e-3)
    u = d / dist
    x = (l1 ** 2 - l2 ** 2 + dist ** 2) / (2 * dist)
    h = np.sqrt(np.clip(l1 ** 2 - x ** 2, 0, None))
    perp = np.c_[-u[:, 1], u[:, 0]]
    perp *= np.sign((perp * flex).sum(1, keepdims=True) + 1e-9)
    return a + u * x + perp * h


def _sigmoide(t, t0, ancho=5.0):
    return 1 / (1 + np.exp(-(t - t0) / ancho))


def simular(estilo='crol', vista='lateral', dur=120.0, fps=30, t_fatiga=70.0, seed=0, ancho_px=1280, alto_px=720,
            metros_encuadre=25.0, px_por_m=None, ruido_px=1.5, perdida=0.06, variacion=0.0, copia_brazos=0.0):
    """Devuelve dict(kps (T,17,2) px, conf (T,17), fps, W, H, verdad DataFrame por fotograma).

    variacion: 0-1, cambia al azar ritmo, alcance y tamaño (para generar nadadores distintos).
    copia_brazos: fracción de fotogramas en los que el brazo oculto copia al visible, como hace YOLO de perfil.
    """
    rng = np.random.default_rng(seed)
    p = PARAMS[estilo]
    T = int(dur * fps)
    t = np.arange(T) / fps
    fat = _sigmoide(t, t_fatiga) if t_fatiga is not None else np.zeros(T)
    var = lambda: 1 + variacion * rng.uniform(-0.15, 0.15)
    periodo = (p['T'][0] + (p['T'][1] - p['T'][0]) * fat) * var()
    v = (p['v'][0] + (p['v'][1] - p['v'][0]) * fat) * var()
    fase = 2 * np.pi * np.cumsum(1 / periodo) / fps + rng.uniform(0, 2 * np.pi)
    esc = var()                                              # tamaño del nadador
    alterno = estilo in ('crol', 'espalda')
    boca_arriba = estilo == 'espalda'
    alcance = (0.62 - 0.12 * fat) * esc * var()
    hundir = 0.06 * fat * esc                                # la cadera se hunde con la fatiga
    asim = 1 - 0.25 * fat                                    # el brazo derecho acorta más
    k = np.zeros((T, 17, 2))                                 # en metros, ejes del cuerpo (ver abajo)
    visible = np.ones(T, bool)

    if vista == 'lateral':
        ppm = px_por_m or ancho_px / metros_encuadre
        # Posición a lo largo de la piscina: largos de 25 m con viraje (1,2 s sin nadador visible junto a la pared)
        s = np.cumsum(v) / fps + 1.0
        largo = metros_encuadre - 2.0
        ida = (s // largo) % 2 == 0
        x = np.where(ida, 1.0 + s % largo, 1.0 + largo - s % largo)
        direc = np.where(ida, 1.0, -1.0)
        visible &= ~((s % largo < 0.9) | (s % largo > largo - 0.9))
        f = np.c_[direc, np.zeros(T)]                        # hacia delante (sentido del nado)
        d = np.tile([0.0, 1.0], (T, 1))                      # hacia el fondo (abajo en la imagen)
        y0 = alto_px / ppm * 0.55
        ond = 0.05 * esc * np.sin(fase) if estilo in ('mariposa', 'braza') else 0.01 * np.sin(2 * fase)
        cad = np.c_[x, np.full(T, y0)] + d * (hundir + ond)[:, None]
        hom = cad + f * TRONCO * esc - d * (0.02 + hundir)[:, None]          # solo se hunde la cadera
        lado = {'I': -0.015, 'D': 0.015}                     # los dos lados casi se superponen de perfil
        for S, H in ((5, 11), (6, 12)):
            off = d * lado['I' if S == 5 else 'D']
            k[:, S], k[:, H] = hom + off, cad + off
        cabeza = hom + f * 0.22 * esc
        k[:, 0] = cabeza + d * (-0.09 if boca_arriba else 0.07) * esc      # boca arriba: la nariz mira a la superficie
        k[:, 1:5] = k[:, [0]] + rng.normal(0, 0.01, (T, 4, 2))
        for (S, E, W), desfase, a_lado in (((5, 7, 9), np.pi if alterno else 0.0, 1.0), ((6, 8, 10), 0.0, asim)):
            ph = fase + desfase
            R = alcance * a_lado
            if estilo == 'braza':                            # tracción corta y poco profunda, delante de la cabeza
                mano = k[:, S] + f * (0.30 + 0.25 * np.cos(ph))[:, None] * esc + d * (0.18 * np.clip(np.sin(ph), 0, None))[:, None] * esc
            else:                                            # elipse: entrada delante, tracción por debajo del cuerpo
                mano = k[:, S] + f * (R * np.cos(ph))[:, None] + d * (0.45 * R / 0.62 * np.sin(ph))[:, None]
            k[:, W] = mano
            k[:, E] = _codo(k[:, S], mano, BRAZO * esc, ANTEBRAZO * esc, d)
        for (Hh, K, A), desfase in (((11, 13, 15), np.pi), ((12, 14, 16), 0.0)):
            if estilo == 'braza':                            # patada de rana: los talones van a los glúteos
                g = 0.5 * (1 - np.cos(fase + np.pi))
                tobillo = k[:, Hh] - f * ((0.88 - 0.45 * g) * esc)[:, None] - d * (0.05 * g * esc)[:, None]
            elif estilo == 'mariposa':                       # patada de delfín: piernas juntas, 2 por ciclo
                tobillo = k[:, Hh] - f * 0.86 * esc + d * (0.16 * esc * np.sin(2 * fase))[:, None]
            else:                                            # patada alterna: 6 por ciclo
                tobillo = k[:, Hh] - f * 0.88 * esc + d * ((0.10 - 0.04 * fat) * esc * np.sin(3 * fase + desfase))[:, None]
            k[:, A] = tobillo
            k[:, K] = _codo(k[:, Hh], tobillo, MUSLO * esc, PIERNA * esc, -d if estilo == 'braza' else d)
    else:                                                    # FRONTAL: cámara delante; x = izquierda-derecha, y = profundidad
        ppm = px_por_m or alto_px / 2.4
        c = np.c_[np.full(T, ancho_px / ppm / 2), np.full(T, alto_px / ppm * 0.42)]
        c[:, 1] += (0.06 * esc * np.sin(fase) if estilo in ('mariposa', 'braza') else 0.0) + hundir
        for S, H, sgn in ((5, 11, 1.0), (6, 12, -1.0)):      # el lado izquierdo del nadador sale a la derecha
            k[:, S] = c + [sgn * 0.21 * esc, 0.0]
            k[:, H] = c + [sgn * 0.15 * esc, 0.07 * esc]     # tronco acortado: la cadera queda detrás
        k[:, 0] = c + [0.0, (-0.13 if boca_arriba else 0.03) * esc]
        k[:, 1:5] = k[:, [0]] + rng.normal(0, 0.01, (T, 4, 2))
        for (S, E, W, sgn), desfase, a_lado in (((5, 7, 9, 1.0), np.pi if alterno else 0.0, 1.0),
                                                 ((6, 8, 10, -1.0), 0.0, asim)):
            ph = fase + desfase
            R = alcance * a_lado
            if estilo == 'braza':                            # barrido hacia fuera y hacia dentro
                mano = k[:, S] + np.c_[sgn * (0.05 + 0.30 * 0.5 * (1 - np.cos(ph))) * esc, 0.10 * esc * np.sin(ph)]
            elif estilo == 'mariposa':                       # recobro ancho por fuera, tracción por debajo
                mano = k[:, S] + np.c_[sgn * (0.10 + 0.25 * np.clip(-np.sin(ph), 0, None)) * esc, 0.75 * R * np.sin(ph)]
            else:                                            # crol y espalda: la mano baja bajo el cuerpo y sube
                mano = k[:, S] + np.c_[-sgn * 0.08 * esc * np.sin(ph), 0.75 * R * np.sin(ph)]
            k[:, W] = mano
            k[:, E] = _codo(k[:, S], mano, BRAZO * esc, ANTEBRAZO * esc, np.c_[np.full(T, sgn), np.zeros(T)])
        for Hh, K, A, sgn, desfase in ((11, 13, 15, 1.0, np.pi), (12, 14, 16, -1.0, 0.0)):
            if estilo == 'braza':
                g = 0.5 * (1 - np.cos(fase + np.pi))
                tobillo = k[:, Hh] + np.c_[sgn * (0.02 + 0.30 * g) * esc, (0.20 - 0.08 * g) * esc]
            elif estilo == 'mariposa':
                tobillo = k[:, Hh] + np.c_[np.full(T, sgn * 0.03 * esc), (0.20 + 0.10 * np.sin(2 * fase)) * esc]
            else:
                tobillo = k[:, Hh] + np.c_[np.full(T, sgn * 0.05 * esc), (0.20 + (0.07 - 0.03 * fat) * np.sin(3 * fase + desfase)) * esc]
            k[:, A] = tobillo
            k[:, K] = _codo(k[:, Hh], tobillo, 0.16 * esc, 0.16 * esc, np.c_[np.full(T, sgn), np.zeros(T)])

    if vista == 'lateral' and copia_brazos > 0:              # error típico del modelo de pose real en vista lateral
        m = rng.random(T) < copia_brazos
        k[np.ix_(m, [7, 9])] = k[np.ix_(m, [8, 10])] + rng.normal(0, 0.01, (m.sum(), 2, 2))
    kps = k * ppm + rng.normal(0, ruido_px, (T, 17, 2))
    conf = np.clip(rng.normal(0.8, 0.08, (T, 17)), 0.35, 0.99)
    conf[rng.random((T, 17)) < perdida] = 0.1               # puntos perdidos sueltos
    conf[~visible] = 0.0
    for t0 in rng.choice(T, size=max(1, int(dur / 30)), replace=False):     # algún hueco de detección
        conf[t0:t0 + int(0.5 * fps)] = 0.0
    kps[conf < 0.3] = np.nan
    verdad = pd.DataFrame(dict(t=t, SR_ciclos_min=60 / periodo, velocidad_m_s=v, DPS_m=v * periodo, fatiga=fat,
                               visible=visible))
    return dict(kps=kps, conf=conf, fps=float(fps), W=ancho_px, H=alto_px, verdad=verdad, px_por_m=ppm,
                estilo=estilo, vista=vista, t_fatiga=t_fatiga)


def dibujar_video(ruta, sim, color_agua=(150, 100, 30)):
    """Vídeo con un fondo de piscina y el nadador dibujado (para poder generar el vídeo anotado del caso ficticio)."""
    import cv2
    W, H, fps, kps = sim['W'], sim['H'], sim['fps'], sim['kps']
    vw = cv2.VideoWriter(str(ruta), cv2.VideoWriter_fourcc(*'mp4v'), fps, (W, H))
    fondo = np.full((H, W, 3), color_agua, np.uint8)
    for i in range(0, H, 40):                                # corcheras y líneas para dar sensación de piscina
        cv2.line(fondo, (0, i), (W, i), (165, 115, 45), 1)
    if sim['vista'] == 'lateral':
        for m in range(0, 26, 5):
            x = int(m * sim['px_por_m'])
            cv2.line(fondo, (x, 0), (x, H), (190, 140, 60), 1)
            cv2.putText(fondo, f'{m} m', (x + 3, H - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (230, 220, 200), 1)
    huesos = [(5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (11, 12), (5, 11), (6, 12), (11, 13), (13, 15), (12, 14), (14, 16)]
    for i in range(len(kps)):
        f = fondo.copy()
        p = kps[i]
        for a, b in huesos:
            if not (np.isnan(p[a]).any() or np.isnan(p[b]).any()):
                cv2.line(f, tuple(int(v) for v in p[a]), tuple(int(v) for v in p[b]), (225, 225, 235), 6, cv2.LINE_AA)
        if not np.isnan(p[0]).any():
            cv2.circle(f, tuple(int(v) for v in p[0]), 9, (225, 225, 235), -1, cv2.LINE_AA)
        vw.write(f)
    vw.release()
