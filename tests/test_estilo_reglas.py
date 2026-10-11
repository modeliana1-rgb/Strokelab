"""Estilo por reglas biomecánicas (estilo.estimar_por_reglas) con puntos reales del participante P1 (crol):
GX011614 (lateral) e IMG_7207 / IMG_7215 (frontal) deben salir con brazos alternos y estilo crol.
Con datos sintéticos de mariposa (lateral) deben salir brazos simultáneos.

Uso:  python tests/test_estilo_reglas.py
"""
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from strokelab import estilo, medidas, simulador, vista  # noqa: E402


def main():
    for clip in ('GX011614', 'IMG_7207', 'IMG_7215'):
        z = np.load(RAIZ / 'tests' / 'datos' / f'aaron_{clip}_keypoints.npz')
        fps = float(z['fps'])
        k2d, _ = medidas.limpiar(z['kps'], z['conf'], fps)
        r = estilo.estimar_por_reglas(k2d, fps, vista.detectar_vista(k2d, fps))
        print(clip, r['estilo'], r['familia'], r['seguridad'], r['medidas'])
        assert r['familia'] == 'alternos' and r['estilo'] == 'crol', (clip, r)
    s = simulador.simular('mariposa', 'lateral', dur=40, seed=5, t_fatiga=None)
    k2d, _ = medidas.limpiar(s['kps'], s['conf'], s['fps'])
    r = estilo.estimar_por_reglas(k2d, s['fps'], vista.detectar_vista(k2d, s['fps']))
    print('mariposa sintética', r['estilo'], r['familia'], r['medidas'])
    assert r['familia'] == 'simultaneos', r
    print('OK: estilo por reglas')


if __name__ == '__main__':
    main()
