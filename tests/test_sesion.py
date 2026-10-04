"""Prueba de sesion.py: el nadador sintético se parte en 3 pasadas (vídeos) y se analiza la sesión completa.

Uso:  python tests/test_sesion.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / 'tests'))
import analizar  # noqa: E402
import sesion  # noqa: E402
from test_local import nadador_sintetico  # noqa: E402


def main():
    tmp = Path(tempfile.mkdtemp())
    kps, conf, fps, W, H = nadador_sintetico()
    carpetas = []
    for n, (a, b) in enumerate([(0, 900), (900, 1800), (1800, 2700)], 1):   # 3 pasadas de 30 s
        out = tmp / f'pasada{n}'
        out.mkdir()
        np.savez(out / 'keypoints_raw.npz', kps=kps[a:b], conf=conf[a:b], fps=fps, w=W, h=H)
        analizar.main([f'pasada{n}.mp4', '--salida', str(out), '--desde-keypoints', '--sin-3d', '--sin-video'])
        carpetas.append(str(out))
    vacia = tmp / 'pasada_vacia'                   # una pasada sin ciclos válidos no debe romper la sesión
    vacia.mkdir()
    np.savez(vacia / 'keypoints_raw.npz', kps=np.full((300, 17, 2), np.nan), conf=np.zeros((300, 17)), fps=fps, w=W, h=H)
    analizar.main(['vacia.mp4', '--salida', str(vacia), '--desde-keypoints', '--sin-3d', '--sin-video'])
    carpetas.insert(1, str(vacia))
    assert sesion.main(carpetas + ['--nadador', 'Sintético', '--salida', str(tmp / 'sesion')]) == 0
    res = json.loads((tmp / 'sesion' / 'resumen_sesion.json').read_text(encoding='utf-8'))
    # la fatiga sintética empieza hacia t = 50 s, es decir, en la 2.ª pasada (30-60 s)
    assert res['inicio_fatiga_pasada'] == 3, res   # la pasada vacía ocupa el lugar 2
    print(f'OK: sesión de 3 pasadas, {res["ciclos"]} ciclos, fatiga en la pasada {res["inicio_fatiga_pasada"]}')


if __name__ == '__main__':
    os.environ.setdefault('MPLBACKEND', 'Agg')
    main()
