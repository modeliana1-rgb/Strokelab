"""Vertical 2 · Limpieza, medidas por fotograma, ciclos de brazada y variables por ciclo.

Las medidas articulares se calculan sobre la pose 3D (MotionBERT) si está disponible, porque no dependen
del ángulo de la cámara (vista lateral, frontal...). Si no, sobre la pose 2D.
"""
import warnings

import numpy as np
import pandas as pd
from scipy.signal import find_peaks, savgol_filter

from .pose import LSH, RSH, LEL, REL, LWR, RWR, LHIP, RHIP, LKN, RKN, LAN, RAN

NOMBRES_ARTIC = ['nariz', 'ojoI', 'ojoD', 'orejaI', 'orejaD', 'hombroI', 'hombroD', 'codoI', 'codoD', 'muñecaI',
                 'muñecaD', 'caderaI', 'caderaD', 'rodillaI', 'rodillaD', 'tobilloI', 'tobilloD']


def limpiar(kps, conf, fps, conf_min=0.30, max_hueco_s=0.4):
    """Filtro por confianza, interpolación de huecos cortos y suavizado Savitzky-Golay por tramos."""
    k = kps.astype(float).copy()
    k[conf < conf_min] = np.nan
    win = max(5, int(fps / 5) | 1)                       # ~0.2 s, impar
    for j in range(17):
        for d in range(k.shape[2]):
            s = pd.Series(k[:, j, d]).interpolate(limit=int(max_hueco_s * fps), limit_area='inside').to_numpy()
            out = s.copy()
            ok = ~np.isnan(s)
            idx = np.flatnonzero(np.diff(np.r_[0, ok.astype(int), 0]))
            for a, b in zip(idx[::2], idx[1::2]):
                if b - a > win:
                    out[a:b] = savgol_filter(s[a:b], win, 2)
            k[:, j, d] = out
    validez = pd.Series(100 * np.mean(~np.isnan(k[:, :, 0]), 0), index=NOMBRES_ARTIC).round(1)
    return k, validez


def angulo(a, b, c):
    """Ángulo en b (grados), en 2D o 3D."""
    v1, v2 = a - b, c - b
    cos = (v1 * v2).sum(-1) / (np.linalg.norm(v1, axis=-1) * np.linalg.norm(v2, axis=-1))
    return np.degrees(np.arccos(np.clip(cos, -1, 1)))


def medidas_por_fotograma(k2d, fps, k3d=None, vista='lateral'):
    """Medidas por fotograma. k2d (T,17,2) limpio; k3d (T,17,3) opcional (MotionBERT, orden COCO).

    De frente y en 2D el tronco aparece acortado: la escala del cuerpo para los filtros es el ancho de hombros.
    """
    warnings.filterwarnings('ignore', 'Mean of empty slice')
    warnings.filterwarnings('ignore', 'All-NaN slice')
    k = k3d if k3d is not None else k2d
    hom = np.nanmean([k[:, LSH], k[:, RSH]], 0)
    cad = np.nanmean([k[:, LHIP], k[:, RHIP]], 0)
    eje = hom - cad
    L = np.linalg.norm(eje, axis=1)
    if vista == 'frontal' and k3d is None:
        L = np.linalg.norm(k[:, LSH] - k[:, RSH], axis=1)

    # Filtro de plausibilidad anatómica: tronco fuera de [0.5, 2] x mediana = cadera/hombro mal detectados
    L_med = np.nanmedian(L)
    malo = ~((L > 0.5 * L_med) & (L < 2.0 * L_med))

    # Dirección del tronco en la imagen: los modelos de pose a veces "ponen de pie" a un nadador horizontal.
    # Se descartan los fotogramas cuyo tronco se desvía más de 45° de la dirección habitual del nadador en el
    # vídeo (estadística axial: nadar hacia la izquierda o hacia la derecha cuenta como la misma dirección).
    e2 = np.nanmean([k2d[:, LSH], k2d[:, RSH]], 0) - np.nanmean([k2d[:, LHIP], k2d[:, RHIP]], 0)
    ang2 = np.arctan2(e2[:, 1], e2[:, 0])
    ok2 = ~np.isnan(ang2)
    desv = np.full(len(ang2), np.nan)
    if ok2.sum() >= 10:
        cand = np.radians(np.arange(0, 180, 2))
        dif = lambda a, b: np.abs((a - b + np.pi / 2) % np.pi - np.pi / 2)      # diferencia axial en [0, 90°]
        ang_hab = cand[np.argmin([dif(ang2[ok2], c).sum() for c in cand])]     # mediana axial (robusta)
        desv = np.degrees(dif(ang2, ang_hab))
    girado = desv > 45
    malo = malo | girado
    L = np.where(malo, np.nan, L)
    u = eje / np.where(np.isnan(L), np.nan, np.linalg.norm(eje, axis=1))[:, None]     # eje del tronco unitario

    def segmentos_ok(a, b, c, lo=0.15, hi=1.3, kk=None, LL=None):
        kk = k if kk is None else kk
        LL = L if LL is None else LL
        s1 = np.linalg.norm(kk[:, b] - kk[:, a], axis=1) / LL
        s2 = np.linalg.norm(kk[:, c] - kk[:, b], axis=1) / LL
        return (s1 > lo) & (s1 < hi) & (s2 > lo) & (s2 < hi)

    brazoI, brazoD = segmentos_ok(LSH, LEL, LWR), segmentos_ok(RSH, REL, RWR)
    piernaI, piernaD = segmentos_ok(LHIP, LKN, LAN, hi=1.6), segmentos_ok(RHIP, RKN, RAN, hi=1.6)
    con = lambda ok, v: np.where(ok & ~np.isnan(L), v, np.nan)

    fr = pd.DataFrame({'t': np.arange(len(k)) / fps})
    fr['codo_I'] = con(brazoI, angulo(k[:, LSH], k[:, LEL], k[:, LWR]))
    fr['codo_D'] = con(brazoD, angulo(k[:, RSH], k[:, REL], k[:, RWR]))
    fr.loc[fr.codo_I < 25, 'codo_I'] = np.nan            # < 25° no es posible: muñeca sobre el hombro
    fr.loc[fr.codo_D < 25, 'codo_D'] = np.nan
    fr['hombro_I'] = con(brazoI, angulo(k[:, LEL], k[:, LSH], k[:, LHIP]))     # brazo respecto al tronco
    fr['hombro_D'] = con(brazoD, angulo(k[:, REL], k[:, RSH], k[:, RHIP]))
    fr['cadera_I'] = con(piernaI, angulo(k[:, LSH], k[:, LHIP], k[:, LKN]))    # 180° = cuerpo recto
    fr['cadera_D'] = con(piernaD, angulo(k[:, RSH], k[:, RHIP], k[:, RKN]))
    fr['rodilla_I'] = con(piernaI, angulo(k[:, LHIP], k[:, LKN], k[:, LAN]))
    fr['rodilla_D'] = con(piernaD, angulo(k[:, RHIP], k[:, RKN], k[:, RAN]))
    fr['munI_eje'] = con(brazoI, ((k[:, LWR] - k[:, LSH]) * u).sum(1) / L)
    fr['munD_eje'] = con(brazoD, ((k[:, RWR] - k[:, RSH]) * u).sum(1) / L)
    # Señal para contar brazadas: SIEMPRE en 2D (lo observado en la imagen; el 3D añade errores del modelo).
    # Se usa la PROFUNDIDAD de la mano: distancia de la muñeca al eje del cuerpo, perpendicular a él y hacia abajo
    # en la imagen. En cada brazada la mano baja por debajo del cuerpo en la tracción y vuelve a subir: un máximo
    # por brazada. Con la mano más profunda de las dos no importa qué brazo es ni si el modelo los confunde
    # (en vista lateral los modelos de pose suelen copiar el brazo visible en el oculto).
    L2 = np.linalg.norm(e2, axis=1)
    L2m = np.nanmedian(L2)
    L2 = np.where((L2 > 0.5 * L2m) & (L2 < 2.0 * L2m) & ~girado, L2, np.nan)
    u2 = e2 / L2[:, None]
    abajo = np.c_[-u2[:, 1], u2[:, 0]]
    abajo = abajo * np.where(abajo[:, 1:2] < 0, -1, 1)    # perpendicular al cuerpo apuntando hacia abajo en la imagen
    okI2 = segmentos_ok(LSH, LEL, LWR, kk=k2d, LL=L2) & ~np.isnan(L2)
    okD2 = segmentos_ok(RSH, REL, RWR, kk=k2d, LL=L2) & ~np.isnan(L2)
    fr['munI_prof2d'] = np.where(okI2, ((k2d[:, LWR] - k2d[:, LSH]) * abajo).sum(1) / L2, np.nan)
    fr['munD_prof2d'] = np.where(okD2, ((k2d[:, RWR] - k2d[:, RSH]) * abajo).sum(1) / L2, np.nan)
    # Vista FRONTAL (el nadador viene hacia la cámara o se le ve desde el borde): la profundidad respecto al eje del
    # cuerpo no se ve, pero cada brazo recorre una trayectoria de ida y vuelta en la imagen (bajar-subir de frente,
    # adelante-atrás desde arriba). Se toma la dirección en la que más se mueven las muñecas respecto al centro de los
    # hombros (componente principal), con sentido hacia abajo en la imagen, y se divide por el ancho de hombros
    # (de frente es más estable que el tronco, que aparece acortado). De frente sí se distinguen los dos brazos.
    hom2 = np.nanmean([k2d[:, LSH], k2d[:, RSH]], 0)
    ancho = np.nanmedian(np.linalg.norm(k2d[:, LSH] - k2d[:, RSH], axis=1))
    rel = [k2d[:, w] - hom2 for w in (LWR, RWR)]
    rel = np.concatenate([r - np.nanmean(r, 0) for r in rel])       # cada brazo centrado: cuenta su recorrido, no su lado
    rel = rel[~np.isnan(rel).any(1)]
    d = np.array([0.0, 1.0])
    if len(rel) >= 10:
        d = np.linalg.svd(rel, full_matrices=False)[2][0]
        d = -d if d[1] < 0 else d
    fr['munI_front'] = ((k2d[:, LWR] - hom2) @ d) / ancho if ancho > 0 else np.nan
    fr['munD_front'] = ((k2d[:, RWR] - hom2) @ d) / ancho if ancho > 0 else np.nan
    fr['sep_tobillos'] = con(piernaI & piernaD, np.linalg.norm(k[:, LAN] - k[:, RAN], axis=1) / L)
    # Inclinación del tronco respecto a la horizontal: solo tiene sentido en 2D con vista lateral
    fr['inclinacion_tronco'] = np.where(np.isnan(L), np.nan, np.degrees(np.arctan2(np.abs(e2[:, 1]), np.abs(e2[:, 0]))))
    fr['cadera_x_px'] = np.nanmean([k2d[:, LHIP], k2d[:, RHIP]], 0)[:, 0]
    fr.attrs['pct_tronco_descartado'] = float(100 * np.mean(malo & ~np.isnan(eje[:, 0])))
    fr.attrs['pct_tronco_girado'] = float(100 * np.mean(girado & ~np.isnan(eje[:, 0])))
    fr.attrs['usa_3d'] = k3d is not None
    return fr


# Brazadas por ciclo y rango fisiológico del tiempo entre brazadas (s) según el estilo. En crol y espalda los brazos
# alternan (1 ciclo = 2 brazadas); en mariposa y braza tiran a la vez (1 ciclo = 1 brazada).
ESTILOS = {
    'crol': dict(brazadas_ciclo=2, t_min=0.35, t_max=1.0),       # 30-85 ciclos/min
    'espalda': dict(brazadas_ciclo=2, t_min=0.35, t_max=1.2),    # 25-85 ciclos/min
    'mariposa': dict(brazadas_ciclo=1, t_min=0.7, t_max=2.0),    # 30-85 ciclos/min
    'braza': dict(brazadas_ciclo=1, t_min=0.7, t_max=2.4),       # 25-85 ciclos/min
}


def periodo_brazada(sig, fps, t_min=0.35, t_max=1.0):
    """Tiempo típico entre brazadas (s): mediana de los intervalos entre máximos consecutivos de la señal.

    Primero se buscan máximos separados al menos t_min; después solo cuentan los intervalos dentro del rango
    fisiológico del crol (0,35-1,0 s entre brazadas, 30-85 ciclos/min), así los huecos de detección no lo alteran.
    Devuelve None si hay menos de 3 intervalos válidos.
    """
    ok = ~np.isnan(sig)
    if ok.sum() < 2 * fps:
        return None
    picos, _ = find_peaks(np.where(ok, sig, np.nanmin(sig)), distance=max(1, int(t_min * fps)),
                          prominence=0.3 * np.nanstd(sig))
    picos = picos[ok[picos]]
    d = np.diff(picos) / fps
    d = d[(d >= t_min) & (d <= t_max)]
    return float(np.median(d)) if len(d) >= 3 else None


def detectar_ciclos(fr, fps, estilo='crol', vista='lateral'):
    """Brazadas = máxima profundidad de la mano en la tracción, de CUALQUIER brazo (la mano más profunda).

    Así no importa si el modelo confunde la muñeca izquierda con la derecha. Un ciclo = dos brazadas seguidas sin
    brazadas perdidas entre medias (en mariposa y braza, un ciclo = una brazada). En vista frontal la señal es el
    recorrido de cada muñeca en la imagen en lugar de su profundidad. Devuelve (señal, picos de brazada, lista de ciclos (inicio, fin), periodo).
    """
    lim = int(0.2 * fps)
    señal = 'front' if vista == 'frontal' else 'prof2d'     # de frente: recorrido de la muñeca (ver medidas_por_fotograma)
    mI = fr[f'munI_{señal}'].interpolate(limit=lim, limit_area='inside').to_numpy()
    mD = fr[f'munD_{señal}'].interpolate(limit=lim, limit_area='inside').to_numpy()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        sig = np.fmax(mI, mD)
    fr['muneca_eje'] = sig
    ok = ~np.isnan(sig)
    est = ESTILOS[estilo]
    T = periodo_brazada(sig, fps, est['t_min'], est['t_max'])
    if ok.sum() < fps or T is None:
        return sig, np.array([], int), [], T
    picos, _ = find_peaks(np.where(ok, sig, np.nanmin(sig)), distance=max(1, int(0.6 * T * fps)),
                          prominence=0.3 * np.nanstd(sig))
    picos = picos[ok[picos]]
    # Un ciclo = 2 brazadas. Cada intervalo entre brazadas detectadas vale 1 brazada (0,5-1,5 T) o 2 si la
    # detección perdió una en medio (1,5-2,6 T). Se forma un ciclo al sumar exactamente 2 brazadas; un hueco
    # mayor corta la cuenta.
    ciclos, i = [], 0
    while i < len(picos) - 1:
        acum, j = 0, i
        while j < len(picos) - 1 and acum < est['brazadas_ciclo']:
            n = (picos[j + 1] - picos[j]) / fps / T
            if not 0.5 <= n <= 2.6:
                break
            acum += 1 if n < 1.5 else 2
            j += 1
        if acum == est['brazadas_ciclo']:
            ciclos.append((picos[i], picos[j]))
            i = j
        else:
            i = max(j, i + 1)
    return sig, picos, ciclos, T


def bajo(x, q=0.10):
    """Mínimo robusto del ciclo (percentil 10): un solo fotograma mal detectado no fija el valor del ciclo."""
    x = x.dropna()
    return float(x.quantile(q)) if len(x) >= 3 else np.nan


def alto(x):
    """Máximo robusto del ciclo (percentil 90)."""
    return bajo(x, 0.90)


def variables_por_ciclo(fr, fps, ciclos_ab, metros_ancho=None, ancho_px=None, estilo='crol', vista='lateral'):
    """Una fila por ciclo válido (0.6-3 s, <= 30 % de datos ausentes en la señal de las muñecas)."""
    frontal = vista == 'frontal'
    # De frente no se ve el avance ni la inclinación del tronco: sin velocidad ni inclinación, y el alcance es el
    # recorrido de cada muñeca en anchos de hombros.
    ppm = (ancho_px / metros_ancho) if metros_ancho and ancho_px and not frontal else None
    eje = 'front' if frontal else 'eje'
    filas = []
    for a, b in ciclos_ab:
        seg = fr.iloc[a:b]
        dur = (b - a) / fps
        if not (0.6 <= dur <= 3.0) or seg.muneca_eje.isna().mean() > 0.3:
            continue
        alcI = seg[f'munI_{eje}'].max() - seg[f'munI_{eje}'].min()
        alcD = seg[f'munD_{eje}'].max() - seg[f'munD_{eje}'].min()
        sep = seg.sep_tobillos.interpolate(limit_area='inside').to_numpy()
        n_patadas = len(find_peaks(sep[~np.isnan(sep)], prominence=0.05)[0]) if np.sum(~np.isnan(sep)) > 5 else np.nan
        f = dict(ciclo=len(filas) + 1, t_inicio_s=round(a / fps, 2), duracion_s=dur, SR_ciclos_min=60 / dur,
                 codo_min_I=bajo(seg.codo_I), codo_min_D=bajo(seg.codo_D),
                 hombro_max_I=alto(seg.hombro_I), hombro_max_D=alto(seg.hombro_D),
                 cadera_media_I=seg.cadera_I.mean(), cadera_media_D=seg.cadera_D.mean(),
                 rodilla_min_I=bajo(seg.rodilla_I), rodilla_min_D=bajo(seg.rodilla_D),
                 alcance_I=alcI, alcance_D=alcD,
                 asimetria_brazos_pct=100 * abs(alcI - alcD) / np.nanmean([alcI, alcD]),
                 inclinacion_tronco=np.nan if frontal else seg.inclinacion_tronco.mean(),
                 amplitud_patada=np.nanmax(sep) if np.sum(~np.isnan(sep)) else np.nan,
                 patadas_por_ciclo=n_patadas)
        if ppm:
            v = abs(np.nanmedian(np.diff(seg.cadera_x_px))) * fps / ppm
            f.update(velocidad_m_s=v, DPS_m=v * dur, SI=v * v * dur)
        filas.append(f)
    ciclos = pd.DataFrame(filas)
    if len(ciclos):
        ciclos['brazadas_min'] = ESTILOS[estilo]['brazadas_ciclo'] * ciclos.SR_ciclos_min
    return ciclos
