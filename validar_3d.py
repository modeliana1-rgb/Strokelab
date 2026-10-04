"""Compara los ángulos articulares 2D y 3D (MotionBERT) de un vídeo ya analizado.

Uso:  python validar_3d.py ..\\resultados\\GX011614_Aaron_v5
Necesita keypoints_raw.npz y keypoints_3d.npy en esa carpeta. Guarda validacion_3d.csv.
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from strokelab import medidas

COLS = ['codo_I', 'codo_D', 'hombro_I', 'hombro_D', 'cadera_I', 'cadera_D', 'rodilla_I', 'rodilla_D']


def main(carpeta):
    warnings.filterwarnings('ignore')
    c = Path(carpeta)
    z = np.load(c / 'keypoints_raw.npz')
    k3 = np.load(c / 'keypoints_3d.npy')
    fps = float(z['fps'])
    k2, _ = medidas.limpiar(z['kps'], z['conf'], fps)
    f2 = medidas.medidas_por_fotograma(k2, fps)
    f3 = medidas.medidas_por_fotograma(k2, fps, k3)
    ambos = f2[COLS].notna().all(1) & f3[COLS].notna().all(1)
    filas = []
    for col in COLS:
        a, b = f2.loc[ambos, col], f3.loc[ambos, col]
        filas.append(dict(angulo=col, mediana_2d=a.median(), mediana_3d=b.median(),
                          p10_p90_2d=f'{a.quantile(.1):.0f}-{a.quantile(.9):.0f}',
                          p10_p90_3d=f'{b.quantile(.1):.0f}-{b.quantile(.9):.0f}',
                          dif_mediana=b.median() - a.median(), correlacion=np.corrcoef(a, b)[0, 1]))
    t = pd.DataFrame(filas).round(2)
    print(f'Fotogramas con ambos válidos: {int(ambos.sum())}')
    print(t.to_string(index=False))
    t.to_csv(c / 'validacion_3d.csv', index=False)


if __name__ == '__main__':
    main(sys.argv[1])
