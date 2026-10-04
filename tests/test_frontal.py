"""Vista frontal: nadador sintético que viene hacia la cámara (crol), con fatiga progresiva centrada en t = 55 s.

De frente el tronco aparece acortado y la mano se mueve arriba y abajo en la imagen (tracción por debajo del cuerpo,
recobro por encima). Verdad: ciclos de 1,35 s -> 1,10 s (media ~ 50 ciclos/min).

Uso:  python tests/test_frontal.py
"""
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from strokelab import fatiga, medidas  # noqa: E402


def nadador_frontal(fps=30, dur=90, seed=1):
    rng = np.random.default_rng(seed)
    T = fps * dur
    t = np.arange(T) / fps
    fat = 1 / (1 + np.exp(-(t - 55) / 4))
    fase = 2 * np.pi * np.cumsum(1 / (1.35 - 0.25 * fat)) / fps
    R = 60 - 20 * fat                                   # tracción más corta con la fatiga
    k = np.zeros((T, 17, 2))
    cx, y0 = 320.0, 150.0
    k[:, 0] = [cx, y0 - 15]
    k[:, 1:5] = k[:, [0]]
    for (S, E, W, H, K, A), lado, off, asim in [((5, 7, 9, 11, 13, 15), -1, np.pi, 1.0),
                                                ((6, 8, 10, 12, 14, 16), 1, 0.0, 1 - 0.3 * fat)]:
        k[:, S] = [cx + lado * 40, y0]
        k[:, H] = [cx + lado * 25, y0 + 25]
        mano = np.c_[cx + lado * (55 + 10 * np.cos(fase + off)), y0 + R * asim * np.sin(fase + off)]
        k[:, W] = mano
        k[:, E] = (k[:, S] + mano) / 2 + np.c_[np.full(T, lado * 12.0), np.zeros(T)]
        patada = 6 * np.sin(3 * (fase + off))
        k[:, K] = np.c_[np.full(T, cx + lado * 20), y0 + 50 + patada]
        k[:, A] = np.c_[np.full(T, cx + lado * 18), y0 + 75 + 2 * patada]
    k += rng.normal(0, 1.2, k.shape)
    conf = np.full((T, 17), 0.8)
    conf[rng.random((T, 17)) < 0.08] = 0.1
    conf[:120] = 0.05                                   # al principio no hay nadador
    k[conf < 0.3] = np.nan
    return k, conf, fps


def main():
    k, conf, fps = nadador_frontal()
    k2d, _ = medidas.limpiar(k, conf, fps)
    fr = medidas.medidas_por_fotograma(k2d, fps)
    _, _, ciclos_ab, _ = medidas.detectar_ciclos(fr, fps, 'crol', 'frontal')
    cic = medidas.variables_por_ciclo(fr, fps, ciclos_ab, estilo='crol', vista='frontal')
    sr = cic.SR_ciclos_min.mean()
    res = fatiga.analizar_fatiga(cic)
    t_ini = res.get('t_inicio')
    print(f'frontal: {len(cic)} ciclos, SR media {sr:.1f} ciclos/min, inicio de fatiga t = {t_ini}')
    assert 44 <= sr <= 56, f'frecuencia mal contada de frente: {sr:.1f}'
    assert t_ini is not None and 40 <= t_ini <= 65, t_ini
    assert cic.inclinacion_tronco.isna().all(), 'de frente no se mide la inclinación del tronco'
    print('\n'.join(fatiga.explicar(cic, res, 'Frontal')))
    print('OK: vista frontal')


if __name__ == '__main__':
    main()
