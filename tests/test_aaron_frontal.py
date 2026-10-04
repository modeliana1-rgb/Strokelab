"""Validación de la vista frontal con datos reales: Aaron, crol, vídeos de móvil IMG_7207 (6,0 s) e IMG_7215 (9,4 s).

Referencia: cuenta manual de Diana Cruz = 8 ciclos en cada clip, contados en el clip entero
(80 y 51 ciclos/min). Se exige que la frecuencia media estimada esté a menos de un 15 % de la cuenta manual.
El sistema solo encuentra parte de los ciclos (el modelo de pose pierde al nadador en parte del clip).

Uso:  python tests/test_aaron_frontal.py
"""
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from strokelab import medidas  # noqa: E402

MANUAL = {'IMG_7207': (8, 6.0), 'IMG_7215': (8, 9.4)}     # (ciclos contados, segundos del clip)


def main():
    for clip, (n_manual, dur) in MANUAL.items():
        z = np.load(RAIZ / 'tests' / 'datos' / f'aaron_{clip}_keypoints.npz')
        fps = float(z['fps'])
        k2d, _ = medidas.limpiar(z['kps'], z['conf'], fps)
        fr = medidas.medidas_por_fotograma(k2d, fps, vista='frontal')
        _, _, ciclos_ab, _ = medidas.detectar_ciclos(fr, fps, 'crol', 'frontal')
        cic = medidas.variables_por_ciclo(fr, fps, ciclos_ab, estilo='crol', vista='frontal')
        ref = 60 * n_manual / dur
        sr = cic.SR_ciclos_min.mean()
        err = 100 * (sr - ref) / ref
        print(f'{clip}: {len(cic)} de {n_manual} ciclos encontrados, SR {sr:.1f} frente a {ref:.1f} manual ({err:+.1f} %)')
        assert abs(err) < 15, f'{clip}: la frecuencia se aleja de la cuenta manual'
    print('OK: vista frontal validada con la cuenta manual')


if __name__ == '__main__':
    main()
