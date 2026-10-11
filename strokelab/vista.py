"""Detección automática de la vista (lateral o frontal) por tramos del vídeo.

Criterio: orientación del tronco (eje cadera-hombros) en la imagen. Con cámara lateral el nadador está horizontal
en la imagen; de frente (viene hacia la cámara o se graba desde el borde) el tronco aparece casi vertical.
Un fotograma suelto no basta: en los vídeos laterales el modelo de pose "pone de pie" a veces al nadador. Por eso
se decide por tramos con la proporción de fotogramas con el tronco a más de 55° de la horizontal.

Medido en los 17 vídeos reales (vista conocida): en los laterales esa proporción es como mucho del 46 %; en los
frontales, como poco del 87 %. Umbral: 65 %, en el centro del hueco. Tramos de 60 s; si dos tramos seguidos tienen
vista distinta, el punto de cambio se ajusta al fotograma que mejor separa ambas vistas.
"""
import numpy as np

LSH, RSH, LHIP, RHIP = 5, 6, 11, 12
ANGULO_VERTICAL = 55.0     # grados respecto a la horizontal de la imagen
UMBRAL_FRACCION = 0.65     # proporción de fotogramas con el tronco vertical para decidir "frontal"
TRAMO_S = 60.0
MIN_FOTOGRAMAS_S = 2.0     # un tramo necesita al menos 2 s con tronco detectado para decidir por sí mismo


def tronco_vertical(k2d):
    """Por fotograma: 1 si el tronco está a más de 55° de la horizontal, 0 si no, NaN si no hay tronco."""
    e = np.nanmean([k2d[:, LSH], k2d[:, RSH]], 0) - np.nanmean([k2d[:, LHIP], k2d[:, RHIP]], 0)
    ang = np.degrees(np.arctan2(np.abs(e[:, 1]), np.abs(e[:, 0])))
    return np.where(np.isnan(ang), np.nan, (ang > ANGULO_VERTICAL).astype(float))


def _decidir(v):
    ok = ~np.isnan(v)
    return ('frontal' if np.mean(v[ok]) >= UMBRAL_FRACCION else 'lateral') if ok.any() else None, \
        (float(np.mean(v[ok])) if ok.any() else np.nan), int(ok.sum())


def detectar_vista(k2d, fps, tramo_s=TRAMO_S):
    """Devuelve una lista de tramos [(inicio, fin, vista, fraccion_vertical)] que cubre todo el vídeo (en fotogramas)."""
    import warnings
    warnings.filterwarnings('ignore', 'Mean of empty slice')
    v = tronco_vertical(k2d)
    T = len(v)
    n = max(1, int(round(T / (tramo_s * fps))))
    bordes = np.linspace(0, T, n + 1).astype(int)
    tramos = []
    for a, b in zip(bordes[:-1], bordes[1:]):
        vista, frac, nok = _decidir(v[a:b])
        tramos.append([a, b, vista if nok >= MIN_FOTOGRAMAS_S * fps else None])
    # tramos sin datos suficientes: toman la vista del vecino (o la del vídeo entero)
    general = _decidir(v)[0] or 'lateral'
    for i, t in enumerate(tramos):
        if t[2] is None:
            vecinos = [tramos[j][2] for j in (i - 1, i + 1) if 0 <= j < len(tramos) and tramos[j][2]]
            t[2] = vecinos[0] if vecinos else general
    # unir tramos seguidos con la misma vista
    unidos = [tramos[0]]
    for t in tramos[1:]:
        if t[2] == unidos[-1][2]:
            unidos[-1][1] = t[1]
        else:
            unidos.append(t)
    # ajustar cada cambio de vista: el corte que menos fotogramas deja en el lado equivocado
    for i in range(len(unidos) - 1):
        izq, der = unidos[i], unidos[i + 1]
        a, b = izq[0], der[1]
        seg = v[a:b]
        ok = ~np.isnan(seg)
        es_front = np.where(ok, seg, 0.0)
        es_lat = np.where(ok, 1 - seg, 0.0)
        mal_izq = np.cumsum(es_front if izq[2] == 'lateral' else es_lat)          # errores si se corta en s
        mal_der = np.cumsum((es_front if der[2] == 'lateral' else es_lat)[::-1])[::-1]
        cand = np.arange(1, len(seg))
        coste = mal_izq[cand - 1] + mal_der[cand]
        s = a + int(cand[np.argmin(coste)]) if len(cand) else izq[1]
        izq[1], der[0] = s, s
    return [(int(a), int(b), vista, _decidir(v[a:b])[1]) for a, b, vista in unidos]


def describir(tramos, fps):
    return ', '.join(f'{vista} {a / fps:.0f}-{b / fps:.0f} s' for a, b, vista, _ in tramos)
