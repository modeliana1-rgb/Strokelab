"""Conteo de ciclos según el estilo: en mariposa (brazos a la vez) 1 ciclo = 1 brazada; en crol, 2.

Se usa el nadador sintético con los dos brazos en fase. Verdad: ciclos de 1,35 s -> 1,10 s (media ~ 50 ciclos/min).

Uso:  python tests/test_estilos.py
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / 'tests'))
from strokelab import medidas  # noqa: E402
from test_local import nadador_sintetico  # noqa: E402


def sr_medio(kps, conf, fps, estilo):
    k2d, _ = medidas.limpiar(kps, conf, fps)
    fr = medidas.medidas_por_fotograma(k2d, fps)
    _, _, ciclos_ab, _ = medidas.detectar_ciclos(fr, fps, estilo)
    cic = medidas.variables_por_ciclo(fr, fps, ciclos_ab, estilo=estilo)
    return cic.SR_ciclos_min.mean(), len(cic), cic.brazadas_min.mean()


def main():
    kps, conf, fps, _, _ = nadador_sintetico(simultaneo=True)
    sr, n, bm = sr_medio(kps, conf, fps, 'mariposa')
    print(f'mariposa: {n} ciclos, SR media {sr:.1f} ciclos/min, {bm:.1f} brazadas/min')
    assert 44 <= sr <= 56, f'mariposa mal contada: {sr:.1f} ciclos/min'
    assert abs(bm - sr) < 1e-6, 'en mariposa brazadas/min = ciclos/min'
    kps, conf, fps, _, _ = nadador_sintetico()
    sr, n, bm = sr_medio(kps, conf, fps, 'crol')
    print(f'crol: {n} ciclos, SR media {sr:.1f} ciclos/min, {bm:.1f} brazadas/min')
    assert 44 <= sr <= 56 and abs(bm - 2 * sr) < 1e-6
    print('OK: ciclos por estilo')


if __name__ == '__main__':
    main()
