"""Nadador simulado y clasificador de estilo.

1) Crol simulado en vista lateral con cámara fija de 25 m: la frecuencia y la velocidad medidas deben estar a menos
   de un 8 % de la verdad (mediana por ciclo) y la fatiga debe detectarse cerca del inicio programado (t = 70 s).
2) Clasificador de estilo con validación agrupada por vídeo sobre 32 vídeos simulados: exactitud por vídeo >= 90 %.

Uso:  python tests/test_simulador_estilo.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from strokelab import estilo, fatiga, medidas, simulador  # noqa: E402


def main():
    s = simulador.simular('crol', 'lateral', dur=120, seed=3, t_fatiga=70.0)
    fps = s['fps']
    k2d, _ = medidas.limpiar(s['kps'], s['conf'], fps)
    fr = medidas.medidas_por_fotograma(k2d, fps)
    _, _, ab, _ = medidas.detectar_ciclos(fr, fps, 'crol')
    cic = medidas.variables_por_ciclo(fr, fps, ab, 25.0, s['W'], 'crol')
    i = (cic.t_inicio_s * fps).astype(int)
    for col in ('SR_ciclos_min', 'velocidad_m_s'):
        err = 100 * np.median(np.abs(cic[col] - s['verdad'][col].to_numpy()[i]) / s['verdad'][col].to_numpy()[i])
        print(f'{col}: error mediano {err:.1f} %')
        assert err < 8, col
    t_ini = fatiga.analizar_fatiga(cic)['t_inicio']
    print(f'inicio de fatiga detectado en t = {t_ini:.1f} s (programado: transición 59-81 s)')
    assert 50 <= t_ini <= 85

    filas = []
    for e in estilo.ESTILOS:
        for vista in ('lateral', 'frontal'):
            for sd in range(4):
                s = simulador.simular(e, vista, dur=30, seed=500 + 11 * sd + estilo.ESTILOS.index(e), t_fatiga=None,
                                      variacion=1.0, copia_brazos=0.5 if vista == 'lateral' else 0.0)
                k2d, _ = medidas.limpiar(s['kps'], s['conf'], s['fps'])
                filas.append(estilo.rasgos_ventanas(k2d, s['fps'], vista).assign(estilo=e, video=f'{e}_{vista}_{sd}'))
    ev = estilo.evaluar(pd.concat(filas, ignore_index=True), n_splits=4)
    print(f'estilo: exactitud por vídeo {ev["exactitud_video"]:.0%}, por ventana {ev["exactitud_ventana"]:.0%}')
    assert ev['exactitud_video'] >= 0.9
    print('OK: simulador y clasificador de estilo')


if __name__ == '__main__':
    main()
