"""Modo en tiempo real (en_vivo.py) con datos sintéticos: crol lateral de 120 s.

Con fatiga programada (transición del 10 % al 90 % entre 59 y 81 s) exige detectarla entre 55 y 95 s; sin fatiga
exige que no haya alarma. Estilo y vista en automático: deben salir crol y lateral.

Uso:  python tests/test_en_vivo.py
"""
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
import en_vivo  # noqa: E402
from strokelab import simulador  # noqa: E402


def correr(t_fatiga, seed):
    s = simulador.simular('crol', 'lateral', dur=120, seed=seed, t_fatiga=t_fatiga, copia_brazos=0.5)
    with tempfile.TemporaryDirectory() as d:
        np.savez(Path(d) / 'keypoints_raw.npz', kps=s['kps'], conf=s['conf'], fps=s['fps'], w=s['W'], h=s['H'])
        with contextlib.redirect_stdout(io.StringIO()):
            en_vivo.main(['sintetico', '--resultados', d, '--sin-ventana', '--salida', d])
        return json.loads((Path(d) / 'resumen_en_vivo.json').read_text(encoding='utf-8'))


def main():
    r = correr(70.0, 41)
    print('con fatiga:', r)
    assert r['estilo'] == 'crol' and r['vista'] == 'lateral', r
    assert r['inicio_fatiga_s'] is not None and 55 <= r['inicio_fatiga_s'] <= 95, r
    r = correr(None, 42)
    print('sin fatiga:', r)
    assert r['inicio_fatiga_s'] is None and r['estado_final'] == 'FRESCO', r
    print('OK: fatiga en tiempo real')


if __name__ == '__main__':
    main()
