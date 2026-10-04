"""Validación con datos reales: Aaron, crol, GX011614 (pose YOLOv8n ya extraída).

Referencia: cuenta manual de Diana Cruz entre los segundos 30 y 40 del vídeo = 9 ciclos (54 ciclos/min).
Se exige que la frecuencia media estimada esté a menos de un 15 % de la cuenta manual.

Uso:  python tests/test_aaron.py
"""
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from strokelab import medidas  # noqa: E402

REF_MANUAL = 54.0      # ciclos/min (9 ciclos en 10 s, segundos 30-40)


def main():
    z = np.load(RAIZ / 'tests' / 'datos' / 'aaron_GX011614_keypoints.npz')
    kps, conf, fps = z['kps'], z['conf'], float(z['fps'])
    k2d, _ = medidas.limpiar(kps, conf, fps)
    fr = medidas.medidas_por_fotograma(k2d, fps)
    sig, picos, ciclos_ab, T = medidas.detectar_ciclos(fr, fps)
    ciclos = medidas.variables_por_ciclo(fr, fps, ciclos_ab)
    t = fr.t.to_numpy()
    brazadas_30_40 = int(((t[picos] >= 30) & (t[picos] < 40)).sum())
    sr = ciclos.SR_ciclos_min.mean()
    err = 100 * abs(sr - REF_MANUAL) / REF_MANUAL
    print(f'Aaron GX011614: {len(ciclos)} ciclos válidos, SR media {sr:.1f} ciclos/min '
          f'(manual {REF_MANUAL:.0f}, error {err:.1f} %), brazadas detectadas entre 30 y 40 s: {brazadas_30_40} (manual 18)')
    assert err < 15, f'la frecuencia se aleja de la cuenta manual: {sr:.1f} frente a {REF_MANUAL}'
    print('OK: frecuencia de ciclo validada con la cuenta manual')


if __name__ == '__main__':
    main()
