"""StrokeLab · informe completo de un nadador y un estilo a partir de los resultados de lote.py.

Uso:  python informe_nadador.py C:\\Users\\user\\StrokeLab\\resultados --nadador Aaron --estilo crol

Salida en resultados/informe_<nadador>_<estilo>/: tabla_clips.csv, tabla_variables.csv, fig_clips.png,
fig_variables.png e informe.txt (texto para la memoria y para el entrenador).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import lote

COLORES = {'gopro': '#2a78d6', 'movil': '#eb6834'}       # paleta categórica validada (azul, naranja)
GRIS = '#c3c2b7'
# Variable del informe: (columnas por ciclo que se promedian, nombre, unidad). Izquierda y derecha se promedian porque
# en vista lateral el modelo de pose copia el brazo visible en el oculto (ver CLAUDE.md).
VARIABLES = [
    (['SR_ciclos_min'], 'Frecuencia de ciclo', 'ciclos/min'),
    (['codo_min_I', 'codo_min_D'], 'Flexión del codo en el agarre', '°'),
    (['hombro_max_I', 'hombro_max_D'], 'Apertura del hombro', '°'),
    (['cadera_media_I', 'cadera_media_D'], 'Ángulo de cadera', '°'),
    (['rodilla_min_I', 'rodilla_min_D'], 'Flexión de rodilla', '°'),
    (['alcance_I', 'alcance_D'], 'Alcance del brazo', 'troncos'),
    (['inclinacion_tronco'], 'Inclinación del tronco', '°'),
    (['amplitud_patada'], 'Amplitud de patada', 'troncos'),
]


def camara(archivo):
    return 'gopro' if archivo.upper().startswith('GX') else 'movil'


def cargar(res_dir, nadador, estilo):
    lista = [f for f in lote.leer_lista(res_dir / 'resumen_lote.csv')
             if f['nadador'] == nadador and f['estilo'] == estilo and f['estado'] == 'ok']
    clips, ciclos = [], []
    for f in lista:
        d = res_dir / Path(f['archivo']).stem
        r = json.loads((d / 'resumen.json').read_text(encoding='utf-8'))
        clips.append(dict(clip=Path(f['archivo']).stem, camara=camara(f['archivo']), vista=f['vista'], sesion=f['sesion'],
                          resolucion=r['resolucion'], fps=round(r['fps']), duracion_s=r['duracion_s'],
                          s_analizable=r.get('s_analizable'), pct_tronco_descartado=r['pct_tronco_descartado'],
                          ciclos_validos=r['ciclos_validos'], SR_media=r.get('SR_media')))
        try:
            c = pd.read_csv(d / 'variables_por_ciclo.csv')
        except (pd.errors.EmptyDataError, FileNotFoundError):
            continue
        if len(c):
            c.insert(0, 'clip', clips[-1]['clip'])
            c.insert(1, 'camara', clips[-1]['camara'])
            c.insert(2, 'vista', clips[-1]['vista'])
            ciclos.append(c)
    ciclos = pd.concat(ciclos, ignore_index=True) if ciclos else pd.DataFrame()
    for cols, nombre, _ in VARIABLES:
        if len(ciclos):
            ciclos[nombre] = ciclos[[c for c in cols if c in ciclos]].mean(axis=1)
    return pd.DataFrame(clips), ciclos


def tabla_variables(ciclos):
    filas = []
    for _, nombre, unidad in VARIABLES:
        x = ciclos[nombre].dropna()
        fila = dict(variable=nombre, unidad=unidad, n_ciclos=len(x), media=x.mean(), desviacion=x.std(),
                    cv_pct=100 * x.std() / abs(x.mean()) if len(x) > 1 and x.mean() else np.nan)
        for cam in ('gopro', 'movil'):
            y = ciclos.loc[ciclos.camara == cam, nombre].dropna()
            fila[f'media_{cam}'] = y.mean() if len(y) else np.nan
        filas.append(fila)
    return pd.DataFrame(filas).round(2)


def graficas(clips, ciclos, titulo, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'axes.spines.top': False, 'axes.spines.right': False, 'axes.edgecolor': '#898781',
                         'axes.grid': True, 'grid.color': '#e8e6df', 'grid.linewidth': 0.6, 'axes.axisbelow': True})

    # 1) Cuánto de cada clip se puede analizar
    fig, ax = plt.subplots(figsize=(8, 0.55 * len(clips) + 1.2), dpi=150)
    y = np.arange(len(clips))[::-1]
    ax.barh(y, clips.duracion_s, color=GRIS, height=0.6, label='duración del clip')
    for yi, (_, c) in zip(y, clips.iterrows()):
        ax.barh(yi, c.s_analizable or 0, color=COLORES[c.camara], height=0.6,
                label='analizable (GoPro)' if c.camara == 'gopro' else 'analizable (móvil)')
        ax.text(c.duracion_s + 0.6, yi, f'{c.ciclos_validos} ciclos', va='center', fontsize=8, color='#52514e')
    ax.set_yticks(y, clips['clip'])
    ax.set_xlabel('segundos')
    ax.set_title(f'{titulo}: tiempo analizable y ciclos válidos por clip', fontsize=10, loc='left')
    h, l = ax.get_legend_handles_labels()
    unicos = dict(zip(l, h))                       # una entrada por cámara
    ax.legend(unicos.values(), unicos.keys(), fontsize=8, frameon=False, loc='lower right')
    ax.set_xlim(0, clips.duracion_s.max() * 1.2)
    fig.tight_layout()
    fig.savefig(out / 'fig_clips.png')
    plt.close(fig)

    # 2) Variables por ciclo, por clip (pequeños múltiplos, un eje cada uno)
    if not len(ciclos):
        return
    orden = [c for c in clips['clip'] if c in set(ciclos['clip'])]
    fig, axs = plt.subplots(2, 4, figsize=(13, 6), dpi=150)
    rng = np.random.default_rng(0)
    for ax, (_, nombre, unidad) in zip(axs.flat, VARIABLES):
        for i, clip in enumerate(orden):
            sub = ciclos[ciclos['clip'] == clip]
            v = sub[nombre].dropna()
            ax.scatter(i + rng.uniform(-0.12, 0.12, len(v)), v, s=22, color=COLORES[sub.camara.iloc[0]],
                       edgecolor='white', linewidth=0.8, zorder=3)
            if len(v):
                ax.plot([i - 0.25, i + 0.25], [v.median()] * 2, color='#0b0b0b', lw=1.5, zorder=4)
        ax.set_xticks(range(len(orden)), orden, rotation=35, fontsize=7, ha='right')
        ax.set_title(f'{nombre} ({unidad})', fontsize=9, loc='left')
        ax.tick_params(axis='y', labelsize=7)
    fig.suptitle(f'{titulo}: valor de cada ciclo (puntos) y mediana por clip (raya). Azul = GoPro, naranja = móvil',
                 fontsize=10, x=0.01, ha='left')
    fig.tight_layout()
    fig.savefig(out / 'fig_variables.png')
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Informe de un nadador y un estilo a partir de los resultados del lote.')
    ap.add_argument('resultados')
    ap.add_argument('--nadador', required=True)
    ap.add_argument('--estilo', default='crol')
    ap.add_argument('--vista', default='lateral', choices=['lateral', 'otra', 'todas'], help='clips cuyas medidas se resumen')
    a = ap.parse_args(argv)
    res_dir = Path(a.resultados)
    out = res_dir / f'informe_{a.nadador}_{a.estilo}'
    out.mkdir(exist_ok=True)

    clips, ciclos = cargar(res_dir, a.nadador, a.estilo)
    if not len(clips):
        print('No hay clips de ese nadador y estilo en resumen_lote.csv')
        return 1
    clips.to_csv(out / 'tabla_clips.csv', index=False, sep=';', encoding='utf-8-sig')
    # Las medidas solo se comparan entre clips con la misma vista: en vista frontal o desde arriba los ángulos 2D se
    # deforman y la profundidad de la mano no se ve. Por defecto, solo los clips laterales.
    if len(ciclos) and a.vista != 'todas':
        ciclos = ciclos[ciclos.vista == a.vista]
    tv = tabla_variables(ciclos) if len(ciclos) else pd.DataFrame()
    tv.to_csv(out / 'tabla_variables.csv', index=False, sep=';', encoding='utf-8-sig')
    if len(ciclos):
        ciclos.to_csv(out / 'ciclos.csv', index=False, sep=';', encoding='utf-8-sig')
    graficas(clips, ciclos, f'{a.nadador} ({a.estilo})', out)

    sesiones = [s for s in lote.leer_lista(res_dir / 'resumen_sesiones.csv')
                if s['nadador'] == a.nadador and s['estilo'] == a.estilo] if (res_dir / 'resumen_sesiones.csv').exists() else []
    texto = [f'INFORME · {a.nadador} · {a.estilo}', '',
             f'Clips: {len(clips)} · grabado {clips.duracion_s.sum():.1f} s · analizable {clips.s_analizable.sum():.1f} s '
             f'({100 * clips.s_analizable.sum() / clips.duracion_s.sum():.0f} %) · ciclos válidos {int(clips.ciclos_validos.sum())}', '',
             clips.to_string(index=False), '', f'Variables por ciclo (clips con vista {a.vista}):', tv.to_string(index=False) if len(tv) else '(sin ciclos)', '',
             'Fatiga por sesión:']
    texto += [f"  {s['sesion']}: {s['videos']} clips, {s['ciclos']} ciclos -> {s.get('explicacion', '')}" for s in sesiones]
    (out / 'informe.txt').write_text('\n'.join(texto), encoding='utf-8')
    print('\n'.join(texto))
    print(f'\nInforme en: {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
