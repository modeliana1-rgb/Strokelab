"""Comprueba que el seguidor de MoveNet devuelve las coordenadas en píxeles del vídeo original.

Usa un "MoveNet falso" que localiza un punto brillante en la imagen que recibe, así se prueba
toda la geometría (recorte, redimensionado y vuelta a coordenadas) sin descargar el modelo.

Uso:  python tests/test_movenet_recorte.py
"""
import os
import cv2
import nbformat
import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
nb = nbformat.read(os.path.join(ROOT, 'notebooks', 'StrokeLab_v3_pipeline.ipynb'), 4)
g = {'np': np, 'cv2': cv2}
celda = next(c.source for c in nb.cells if c.cell_type == 'code' and 'class SeguidorMoveNet' in c.source)
exec(celda, g)
SeguidorMoveNet = g['SeguidorMoveNet']


def movenet_falso(rgb):
    """Devuelve las 17 articulaciones en el centroide del punto brillante, normalizado [y, x]."""
    gris = rgb.astype(float).sum(2)
    ys, xs = np.nonzero(gris > 0.5 * gris.max())
    tam = rgb.shape[0]
    return np.tile([ys.mean() / tam, xs.mean() / tam, 0.9], (17, 1))


W, H = 3840, 2160
errores = []
for (px, py) in [(1920, 1080), (300, 200), (3700, 2050), (2500, 900)]:
    frame = np.zeros((H, W, 3), np.uint8)
    cv2.circle(frame, (px, py), 40, (255, 255, 255), -1)
    seg = SeguidorMoveNet(movenet_falso, 192, W, H)
    for paso in range(3):  # 1.º fotograma completo, después recortes alrededor del nadador
        xy, sc = seg(frame)
        err = float(np.hypot(xy[0, 0] - px, xy[0, 1] - py))
        lado = seg.region[2] if seg.region else max(W, H)
        errores.append(err)
        print(f'punto ({px},{py}) paso {paso}: estimado ({xy[0,0]:.0f},{xy[0,1]:.0f})  error {err:.1f} px  siguiente recorte {lado:.0f} px')
    assert seg.region is not None and seg.region[2] < max(W, H), 'el seguidor debería recortar alrededor del nadador'

# Error máximo tolerado: ~1 píxel de la imagen de 192 px en el recorte más grande (3840/192 = 20 px)
assert max(errores) < 25, max(errores)
print('OK: coordenadas MoveNet correctas en el vídeo original')
