"""StrokeLab · fatiga a lo largo de una SESIÓN: varias pasadas (vídeos) del mismo nadador, en orden.

Cada clip de GoPro suele recoger una sola pasada (10-20 s de nado): demasiado poco para ver fatiga. Si los clips
son de la misma sesión, se analizan juntos: las primeras pasadas son el estado fresco y las siguientes muestran
cómo cambia la técnica.

Uso (primero se analiza cada vídeo con analizar.py; después):
  python sesion.py ..\\resultados\\GX011614_Aaron ..\\resultados\\GX011617_Aaron ..\\resultados\\GX011618_Aaron --nadador "Aaron"
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from strokelab import fatiga


def main(argv=None):
    ap = argparse.ArgumentParser(description='Fatiga a lo largo de varias pasadas del mismo nadador.')
    ap.add_argument('carpetas', nargs='+', help='carpetas de resultados de analizar.py, EN ORDEN DE GRABACIÓN')
    ap.add_argument('--nadador', default='Nadador')
    ap.add_argument('--salida', help='carpeta de salida (por defecto resultados/sesion_<nadador>)')
    a = ap.parse_args(argv)

    partes, t0 = [], 0.0
    for n, c in enumerate(a.carpetas, 1):
        c = Path(c)
        res = json.loads((c / 'resumen.json').read_text(encoding='utf-8'))
        try:
            cic = pd.read_csv(c / 'variables_por_ciclo.csv')
        except (pd.errors.EmptyDataError, FileNotFoundError):   # vídeo sin ciclos válidos
            cic = pd.DataFrame()
        print(f'  pasada {n}: {res["video"]:<16} {len(cic):3d} ciclos válidos')
        if len(cic):
            cic = cic.drop(columns=['anomalia', 'estado'], errors='ignore')
            cic.insert(0, 'pasada', n)
            cic.insert(1, 'video', res['video'])
            cic['t_video_s'] = cic.t_inicio_s
            cic['t_inicio_s'] = cic.t_inicio_s + t0        # tiempo acumulado de la sesión (solo para ordenar y graficar)
            partes.append(cic)
        t0 += res['duracion_s']
    if not partes:
        print('Ninguna pasada tiene ciclos válidos.')
        return 1
    ciclos = pd.concat(partes, ignore_index=True)
    ciclos['ciclo'] = range(1, len(ciclos) + 1)
    out = Path(a.salida) if a.salida else Path('resultados') / f'sesion_{a.nadador}'
    out.mkdir(parents=True, exist_ok=True)
    print(f'\nSesión de {a.nadador}: {len(a.carpetas)} pasadas, {len(ciclos)} ciclos')

    res = fatiga.analizar_fatiga(ciclos)
    if 'anom' in res:
        ciclos['anomalia'] = res['anom']
        ciclos['estado'] = ['fatigado' if res['inicio'] is not None and i >= res['inicio'] else 'fresco'
                            for i in range(len(ciclos))]
        pd.DataFrame(res['shap'], columns=res['feats']).to_csv(out / 'shap_por_ciclo.csv', index=False)
        fatiga.graficas(ciclos, res, f'{a.nadador} (sesión)', out)
    texto = fatiga.explicar(ciclos, res, a.nadador)
    if res.get('inicio') is not None:
        c = ciclos.iloc[res['inicio']]
        texto.insert(1, f'  (pasada {int(c.pasada)}, vídeo {c.video}, segundo {c.t_video_s:.1f} del clip)')
    print('\n' + '\n'.join(texto))
    ciclos.to_csv(out / 'variables_por_ciclo_sesion.csv', index=False)
    print('\nMedias por pasada:')
    cols = [f for f in res.get('feats', []) if f in ciclos][:8]
    print(ciclos.groupby('pasada')[cols].mean().round(1).to_string())
    resumen = dict(nadador=a.nadador, pasadas=[str(c) for c in a.carpetas], ciclos=len(ciclos),
                   inicio_fatiga_ciclo=None if res.get('inicio') is None else int(ciclos.ciclo.iloc[res['inicio']]),
                   inicio_fatiga_pasada=None if res.get('inicio') is None else int(ciclos.pasada.iloc[res['inicio']]),
                   cambio_pelt=res.get('cambio_pelt', []), variables_modelo=res.get('feats', []), explicacion=texto)
    (out / 'resumen_sesion.json').write_text(json.dumps(resumen, ensure_ascii=False, indent=2, default=float), encoding='utf-8')
    print(f'\nResultados en: {out.resolve()}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
