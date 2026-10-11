"""Vista automática (--vista auto) con datos sintéticos: 90 s de crol en vista lateral seguidos de 90 s en vista
frontal, en el mismo "vídeo". Exige que el sistema encuentre los dos tramos (cambio a 90 ± 5 s) y que la
frecuencia de ciclo de cada tramo esté a menos de un 15 % de la referencia.

Uso:  python tests/test_vista_auto.py
"""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
import analizar  # noqa: E402
from strokelab import simulador  # noqa: E402


def main():
    lat = simulador.simular('crol', 'lateral', dur=90, seed=21, t_fatiga=None)
    fro = simulador.simular('crol', 'frontal', dur=90, seed=22, t_fatiga=None)
    kps = np.concatenate([lat['kps'], fro['kps']])
    conf = np.concatenate([lat['conf'], fro['conf']])
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        d = Path(d)
        np.savez(d / 'mixto.npz', kps=kps, conf=conf, fps=lat['fps'], w=lat['W'], h=lat['H'])
        analizar.main(['mixto.mp4', '--keypoints', str(d / 'mixto.npz'), '--salida', str(d / 'res'), '--sin-3d',
                       '--sin-video', '--vista', 'auto', '--nadador', 'Datos sintéticos'])
        res = json.loads((d / 'res' / 'resumen.json').read_text(encoding='utf-8'))
        import pandas as pd
        ciclos = pd.read_csv(d / 'res' / 'variables_por_ciclo.csv')
    tramos = res['tramos_vista']
    print('\nTramos:', tramos)
    assert [t['vista'] for t in tramos] == ['lateral', 'frontal'], tramos
    assert abs(tramos[0]['fin_s'] - 90) <= 5, tramos
    for vista, s in (('lateral', lat), ('frontal', fro)):
        c = ciclos[ciclos.vista == vista]
        verdad = s['verdad'].SR_ciclos_min.mean()
        err = 100 * abs(c.SR_ciclos_min.median() - verdad) / verdad
        print(f'{vista}: {len(c)} ciclos, frecuencia {c.SR_ciclos_min.median():.1f} frente a {verdad:.1f} ({err:.1f} %)')
        assert len(c) >= 20 and err < 15, (vista, len(c), err)
    print('OK: vista automática por tramos')


if __name__ == '__main__':
    main()
