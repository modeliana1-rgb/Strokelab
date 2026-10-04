"""Prueba de lote.py: crea la lista, analiza 3 vídeos (pose ya extraída, del nadador sintético) y une la sesión.

Uso:  python tests/test_lote.py
"""
import csv
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / 'tests'))
import lote  # noqa: E402
from test_local import nadador_sintetico  # noqa: E402


def main():
    tmp = Path(tempfile.mkdtemp())
    vids, res = tmp / 'videos', tmp / 'resultados'
    vids.mkdir()
    kps, conf, fps, W, H = nadador_sintetico()
    for nombre, (a, b) in zip(['GX011614', 'GX011617', 'GX011618'], [(0, 900), (900, 1800), (1800, 2700)]):
        (vids / f'{nombre}.MP4').write_bytes(b'')          # el vídeo no se lee: la pose ya está extraída
        (res / nombre).mkdir(parents=True)
        np.savez(res / nombre / 'keypoints_raw.npz', kps=kps[a:b], conf=conf[a:b], fps=fps, w=W, h=H)
    (vids / 'OTRO.mov').write_bytes(b'')
    assert lote.main(['--carpeta', str(vids), '--crear-lista']) == 0
    filas = lote.leer_lista(vids / 'lista_videos.csv')
    assert [f['nadador'] for f in filas] == ['Aaron'] * 3 + ['?'], filas
    for f in filas:                                         # Diana marca el desconocido como "no incluir"
        if f['archivo'] == 'OTRO.mov':
            f['incluir'] = 'no'
    with open(vids / 'lista_videos.csv', 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.DictWriter(fh, fieldnames=lote.COLUMNAS, delimiter=';'); w.writeheader(); w.writerows(filas)
    assert lote.main(['--carpeta', str(vids)]) == 0
    tabla = lote.leer_lista(res / 'resumen_lote.csv')
    assert len(tabla) == 3 and all(f['estado'] == 'ok' for f in tabla), tabla
    ses = lote.leer_lista(res / 'resumen_sesiones.csv')
    assert ses[0]['sesion'] == 'Aaron_crol_gopro' and ses[0]['inicio_fatiga_pasada'] == '2', ses
    assert (res / 'para_claude.zip').exists()
    print('OK: lote de 3 vídeos y sesión con fatiga en la pasada 2')


if __name__ == '__main__':
    os.environ.setdefault('MPLBACKEND', 'Agg')
    main()
