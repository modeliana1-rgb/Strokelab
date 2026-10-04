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


def medidas_por_fotograma(k2d, fps, k3d=None):
    """Medidas por fotograma. k2d (T,17,2) limpio; k3d (T,17,3) opcional (MotionBERT, orden COCO)."""
    warnings.filterwarnings('ignore', 'Mean of empty slice')
    warnings.filterwarnings('ignore', 'All-NaN slice')
    k = k3d if k3d is not None else k2d
    hom = np.nanmean([k[:, LSH], k[:, RSH]], 0)
    cad = np.nanmean([k[:, LHIP], k[:, RHIP]], 0)
    eje = hom - cad
    L = np.linalg.norm(eje, axis=1)

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
    u = eje / L[:, None]

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
    # Señal para contar brazadas: SIEMPRE en 2D. El momento en que entra la mano se ve directamente en la imagen;
    # el 3D es una estimación que añade errores (p. ej. confundir el brazo izquierdo con el derecho).
    if k3d is None:
        fr['munI_eje2d'], fr['munD_eje2d'] = fr.munI_eje, fr.munD_eje
    else:
        L2 = np.linalg.norm(e2, axis=1)
        L2m = np.nanmedian(L2)
        L2 = np.where((L2 > 0.5 * L2m) & (L2 < 2.0 * L2m) & ~girado, L2, np.nan)
        u2 = e2 / L2[:, None]
        okI2 = segmentos_ok(LSH, LEL, LWR, kk=k2d, LL=L2) & ~np.isnan(L2)
        okD2 = segmentos_ok(RSH, REL, RWR, kk=k2d, LL=L2) & ~np.isnan(L2)
        fr['munI_eje2d'] = np.where(okI2, ((k2d[:, LWR] - k2d[:, LSH]) * u2).sum(1) / L2, np.nan)
        fr['munD_eje2d'] = np.where(okD2, ((k2d[:, RWR] - k2d[:, RSH]) * u2).sum(1) / L2, np.nan)
    fr['sep_tobillos'] = con(piernaI & piernaD, np.linalg.norm(k[:, LAN] - k[:, RAN], axis=1) / L)
    # Inclinación del tronco respecto a la horizontal: solo tiene sentido en 2D con vista lateral
    fr['inclinacion_tronco'] = np.where(np.isnan(L), np.nan, np.degrees(np.arctan2(np.abs(e2[:, 1]), np.abs(e2[:, 0]))))
    fr['cadera_x_px'] = np.nanmean([k2d[:, LHIP], k2d[:, RHIP]], 0)[:, 0]
    fr.attrs['pct_tronco_descartado'] = float(100 * np.mean(malo & ~np.isnan(eje[:, 0])))
    fr.attrs['pct_tronco_girado'] = float(100 * np.mean(girado & ~np.isnan(eje[:, 0])))
    fr.attrs['usa_3d'] = k3d is not None
    return fr


def periodo_brazada(sig, fps, t_min=0.35, t_max=1.0):
    """Periodo típico entre brazadas (s) por autocorrelación de la señal (ignorando huecos).

    1. Se suaviza la señal (media móvil de ~0,15 s) para quitar el temblor fotograma a fotograma.
    2. Se busca el pico de autocorrelación más alto DENTRO del rango fisiológico del crol (0,35-1,0 s entre
       brazadas, 30-85 ciclos/min). Un valor pegado al borde del rango no es un ritmo real y se descarta.
    Devuelve None si no hay un ritmo claro.
    """
    ok = ~np.isnan(sig)
    if ok.sum() < 3 * fps:
        return None
    x = np.where(ok, sig - np.nanmean(sig), 0.0)
    m = ok.astype(float)
    w = np.ones(max(3, int(0.15 * fps) | 1))
    num, den = np.convolve(x, w, 'same'), np.convolve(m, w, 'same')
    x = np.where(ok & (den > 0), num / np.maximum(den, 1e-9), 0.0)
    lags = np.arange(max(1, int(t_min * fps) - 1), int(t_max * fps) + 2)
    acf = np.full(len(lags), -np.inf)
    for n, L in enumerate(lags):
        pares = (m[:-L] * m[L:]).sum()
        if pares > fps:
            acf[n] = (x[:-L] * x[L:]).sum() / pares
    finito = np.isfinite(acf)
    if finito.sum() < 3:
        return None
    picos, _ = find_peaks(np.where(finito, acf, np.nanmin(acf[finito])))
    picos = [p for p in picos if acf[p] > 0 and t_min <= lags[p] / fps <= t_max]
    if not picos:
        return None
    return lags[max(picos, key=lambda p: acf[p])] / fps


def detectar_ciclos(fr, fps):
    """Brazadas = entradas de mano de CUALQUIER brazo (máximo de las dos muñecas sobre el eje del cuerpo).

    Así no importa si el modelo confunde la muñeca izquierda con la derecha. Un ciclo = dos brazadas seguidas sin
    brazadas perdidas entre medias. Devuelve (señal, picos de brazada, lista de ciclos (inicio, fin), periodo).
    """
    lim = int(0.2 * fps)
    mI = fr.munI_eje2d.interpolate(limit=lim, limit_area='inside').to_numpy()
    mD = fr.munD_eje2d.interpolate(limit=lim, limit_area='inside').to_numpy()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        sig = np.fmax(mI, mD)
    fr['muneca_eje'] = sig
    ok = ~np.isnan(sig)
    T = periodo_brazada(sig, fps)
    if ok.sum() < fps or T is None:
        return sig, np.array([], int), [], T
    picos, _ = find_peaks(np.where(ok, sig, np.nanmin(sig)), distance=max(1, int(0.6 * T * fps)),
                          prominence=0.3 * np.nanstd(sig))
    picos = picos[ok[picos]]
    ciclos, i = [], 0
    while i + 2 < len(picos) + 0:
        d1, d2 = (picos[i + 1] - picos[i]) / fps, (picos[i + 2] - picos[i + 1]) / fps
        if 0.5 * T <= d1 <= 1.6 * T and 0.5 * T <= d2 <= 1.6 * T:
            ciclos.append((picos[i], picos[i + 2]))
            i += 2
        else:
            i += 1
    return sig, picos, ciclos, T


def variables_por_ciclo(fr, fps, ciclos_ab, metros_ancho=None, ancho_px=None):
    """Una fila por ciclo válido (0.6-3 s, <= 30 % de datos ausentes en la señal de las muñecas)."""
    ppm = (ancho_px / metros_ancho) if metros_ancho and ancho_px else None
    filas = []
    for a, b in ciclos_ab:
        seg = fr.iloc[a:b]
        dur = (b - a) / fps
        if not (0.6 <= dur <= 3.0) or seg.muneca_eje.isna().mean() > 0.3:
            continue
        alcI = seg.munI_eje.max() - seg.munI_eje.min()
        alcD = seg.munD_eje.max() - seg.munD_eje.min()
        sep = seg.sep_tobillos.interpolate(limit_area='inside').to_numpy()
        n_patadas = len(find_peaks(sep[~np.isnan(sep)], prominence=0.05)[0]) if np.sum(~np.isnan(sep)) > 5 else np.nan
        f = dict(ciclo=len(filas) + 1, t_inicio_s=round(a / fps, 2), duracion_s=dur, SR_ciclos_min=60 / dur,
                 codo_min_I=seg.codo_I.min(), codo_min_D=seg.codo_D.min(),
                 hombro_max_I=seg.hombro_I.max(), hombro_max_D=seg.hombro_D.max(),
                 cadera_media_I=seg.cadera_I.mean(), cadera_media_D=seg.cadera_D.mean(),
                 rodilla_min_I=seg.rodilla_I.min(), rodilla_min_D=seg.rodilla_D.min(),
                 alcance_I=alcI, alcance_D=alcD,
                 asimetria_brazos_pct=100 * abs(alcI - alcD) / np.nanmean([alcI, alcD]),
                 inclinacion_tronco=seg.inclinacion_tronco.mean(),
                 amplitud_patada=np.nanmax(sep) if np.sum(~np.isnan(sep)) else np.nan,
                 patadas_por_ciclo=n_patadas)
        if ppm:
            v = abs(np.nanmedian(np.diff(seg.cadera_x_px))) * fps / ppm
            f.update(velocidad_m_s=v, DPS_m=v * dur, SI=v * v * dur)
        filas.append(f)
    ciclos = pd.DataFrame(filas)
    if len(ciclos):
        ciclos['brazadas_min'] = 2 * ciclos.SR_ciclos_min
    return ciclos
