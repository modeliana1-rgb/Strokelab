"""Fatiga por repeticiones de una serie (por ejemplo 15 × 100 m): paso de cada repetición, ritmo y técnica.

Cada repetición se define por el segundo del vídeo en que empieza y en que termina (los descansos no cuentan).
El paso sale solo de esos tiempos, así que es fiable aunque la cámara no vea al nadador todo el rato.
La fase fresca son las primeras repeticiones (--base, por defecto 3): se compara cada repetición con ellas y se
pasa el mismo detector de fatiga (Isolation Forest + percentil 95 + 3 ciclos seguidos + SHAP).

Uso:
  python analizar_series.py resultados/GX010731 --reps reps.csv [--metros 100] [--base 3] [--nadador Alvise]
reps.csv: una fila por repetición con columnas  inicio_s,fin_s  (segundos del vídeo; separador coma o punto y coma).
También vale  --reps-texto "352-420 470-538 ..."  en lugar de un archivo.
Escribe en <resultados>/por_series/: series.csv, informe_series.txt y fig_series.png.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from strokelab import fatiga

TECNICA = ['codo_min_I', 'codo_min_D', 'hombro_max_I', 'hombro_max_D', 'cadera_media_I', 'cadera_media_D',
           'rodilla_min_I', 'rodilla_min_D', 'inclinacion_tronco', 'amplitud_patada', 'patadas_por_ciclo']


def leer_reps(a):
    if a.reps_texto:
        pares = [p.split('-') for p in a.reps_texto.split()]
        return pd.DataFrame([(float(x), float(y)) for x, y in pares], columns=['inicio_s', 'fin_s'])
    r = pd.read_csv(a.reps, sep=None, engine='python')
    r.columns = [c.strip().lower() for c in r.columns]
    return r[['inicio_s', 'fin_s']].astype(float)


def mmss(s):
    return f'{int(s // 60)}:{s % 60:04.1f}'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('resultados', help='carpeta con variables_por_ciclo.csv')
    ap.add_argument('--reps', help='CSV con inicio_s,fin_s de cada repetición')
    ap.add_argument('--reps-texto', help='repeticiones como "inicio-fin inicio-fin ..." en segundos del vídeo')
    ap.add_argument('--metros', type=float, default=100.0, help='metros de cada repetición')
    ap.add_argument('--base', type=int, default=3, help='repeticiones que forman la fase fresca')
    ap.add_argument('--nadador', default='')
    a = ap.parse_args(argv)
    if not (a.reps or a.reps_texto):
        ap.error('hace falta --reps o --reps-texto')

    carpeta = Path(a.resultados)
    ciclos = pd.read_csv(carpeta / 'variables_por_ciclo.csv')
    reps = leer_reps(a).sort_values('inicio_s').reset_index(drop=True)
    reps['rep'] = np.arange(1, len(reps) + 1)
    out = carpeta / 'por_series'
    out.mkdir(exist_ok=True)

    t = ciclos.t_inicio_s.to_numpy()
    ciclos['rep'] = 0
    for _, r in reps.iterrows():
        ciclos.loc[(t >= r.inicio_s) & (t < r.fin_s), 'rep'] = int(r.rep)
    c = ciclos[ciclos.rep > 0].reset_index(drop=True)

    reps['tiempo_s'] = reps.fin_s - reps.inicio_s
    reps['paso'] = reps.tiempo_s.map(mmss)
    reps['velocidad_m_s'] = (a.metros / reps.tiempo_s).round(3)
    reps['ciclos_medidos'] = reps.rep.map(c.groupby('rep').size()).fillna(0).astype(int)
    reps['SR_mediana'] = reps.rep.map(c.groupby('rep').SR_ciclos_min.median()).round(1)
    tec = [v for v in TECNICA if v in c and c[v].notna().mean() >= 0.5]
    for v in tec:
        reps[v] = reps.rep.map(c.groupby('rep')[v].median()).round(1)
    base_t = reps.tiempo_s.iloc[:a.base].mean()
    reps['vs_fresco_s'] = (reps.tiempo_s - base_t).round(1)

    lineas = [f'{a.nadador or carpeta.name}: {len(reps)} repeticiones de {a.metros:g} m; fase fresca = '
              f'repeticiones 1-{a.base} (paso medio {mmss(base_t)}).', '',
              reps[['rep', 'inicio_s', 'fin_s', 'paso', 'vs_fresco_s', 'velocidad_m_s', 'ciclos_medidos', 'SR_mediana'] + tec]
              .to_string(index=False), '']
    # Mantiene el paso: repeticiones dentro de ±2 % del paso fresco
    dentro = (reps.tiempo_s - base_t).abs() <= 0.02 * base_t
    lineas.append(f'Repeticiones dentro de ±2 % del paso fresco: {int(dentro.sum())} de {len(reps)} '
                  f'({", ".join(str(int(x)) for x in reps.rep[dentro])}).')
    pend = np.polyfit(reps.rep, reps.tiempo_s, 1)[0]
    lineas.append(f'Tendencia del paso: {pend:+.2f} s por repetición ({pend * (len(reps) - 1):+.1f} s de la primera a la última).')

    n_base = int((c.rep <= a.base).sum())
    res = None
    if n_base >= 5 and len(c) - n_base >= 3:
        res = fatiga.analizar_fatiga(c, frac_base=0.0, min_base=n_base)
        lineas += [''] + fatiga.explicar(c, res, a.nadador or carpeta.name)
        if 'anom' in res:
            c['anomalia_series'] = res['anom']
            por_rep = c.groupby('rep').anomalia_series.median()
            reps['anomalia_mediana'] = reps.rep.map(por_rep).round(3)
            reps['ciclos_sobre_umbral'] = reps.rep.map(c.assign(s=c.anomalia_series > res['umbral']).groupby('rep').s.sum()).fillna(0).astype(int)
            lineas += ['', 'Anomalía por repetición (respecto a las frescas; umbral ' f'{res["umbral"]:.3f}):',
                       reps[['rep', 'paso', 'ciclos_medidos', 'anomalia_mediana', 'ciclos_sobre_umbral']].to_string(index=False)]
    else:
        lineas.append(f'Detector: hacen falta al menos 5 ciclos en las repeticiones frescas y 3 después (hay {n_base} y {len(c) - n_base}).')

    reps.to_csv(out / 'series.csv', index=False)
    c.to_csv(out / 'variables_por_ciclo_series.csv', index=False)
    grafica(reps, c, res, base_t, a.base, out / 'fig_series.png', a.nadador or carpeta.name)
    texto = '\n'.join(lineas)
    (out / 'informe_series.txt').write_text(texto + '\n', encoding='utf-8')
    print(texto)
    print(f'\nResultados en {out}')
    return 0


def grafica(reps, c, res, base_t, base, ruta, nombre):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(3, 1, figsize=(10, 8.5), sharex=True)
    col = ['#2a78d6' if r <= base else '#eb6834' for r in reps.rep]
    ax[0].bar(reps.rep, reps.tiempo_s, color=col)
    ax[0].axhline(base_t, color='k', ls='--', lw=1, label='paso fresco')
    lo, hi = reps.tiempo_s.min(), reps.tiempo_s.max()
    ax[0].set_ylim(lo - (hi - lo) * 0.8 - 1, hi + (hi - lo) * 0.3 + 0.5)
    ax[0].set_ylabel('tiempo (s)')
    ax[0].set_title(f'{nombre}: tiempo de cada repetición')
    ax[0].legend(loc='upper left', fontsize=8)
    ax[1].plot(c.rep + np.random.default_rng(0).uniform(-.15, .15, len(c)), c.SR_ciclos_min, 'o', color='#2a78d6', alpha=.5)
    ax[1].plot(reps.rep, reps.SR_mediana, '-', color='k', lw=2, label='mediana')
    ax[1].set_ylabel('ciclos/min')
    ax[1].set_title('Frecuencia de brazos')
    if res is not None and 'anom' in res:
        ax[2].plot(c.rep + np.random.default_rng(1).uniform(-.15, .15, len(c)), res['anom'], 'o', color='#eb6834', alpha=.6)
        ax[2].axhline(res['umbral'], color='k', ls='--', lw=1, label='umbral (p95 repeticiones frescas)')
        ax[2].legend(loc='upper left', fontsize=8)
    ax[2].set_ylabel('anomalía')
    ax[2].set_title('Cuánto se aparta cada ciclo de las repeticiones frescas')
    ax[2].set_xlabel('repetición')
    ax[2].set_xticks(reps.rep)
    fig.tight_layout()
    fig.savefig(ruta, dpi=130)
    plt.close(fig)


if __name__ == '__main__':
    raise SystemExit(main())
