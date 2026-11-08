"""Fatiga por largos: la fase fresca son los primeros largos de la prueba, no el primer 30 % de los ciclos.

Pensado para una prueba con largos conocidos (por ejemplo un 100 m en piscina de 25 m). La hipótesis se fija de
antemano: los largos 1-2 son el estado fresco y se mira si los largos 3-4 se apartan de él. No se ajusta ningún
umbral para que salga fatiga: el detector es el mismo (Isolation Forest + percentil 95 + 3 ciclos seguidos + SHAP),
solo cambia qué ciclos forman la fase base.

Además, con los tiempos de paso por la pared (que se leen en el vídeo) se calcula la velocidad media de cada largo,
que no depende de la pose: es la medida directa de si el nadador pierde velocidad.

Uso:
  python analizar_por_largos.py resultados/demo_rapido --pasos 15.2 33.0 52.1 72.0
      --pasos: segundos del vídeo en que el nadador toca la pared al final de cada largo (25, 50, 75 y 100 m).
      Opcional: --salida <empieza> (segundo de la salida; por defecto 0), --base-largos 2, --metros-largo 25.
Escribe en <resultados>/por_largos/: largos.csv, variables_por_largo.csv, comparacion.csv, fig_largos.png,
informe_largos.txt.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from strokelab import fatiga

VARIABLES = ['SR_ciclos_min', 'alcance_I', 'alcance_D', 'asimetria_brazos_pct', 'amplitud_patada', 'patadas_por_ciclo',
             'codo_min_I', 'codo_min_D', 'hombro_max_I', 'hombro_max_D', 'cadera_media_I', 'cadera_media_D',
             'rodilla_min_I', 'rodilla_min_D', 'inclinacion_tronco']


def asignar_largos(ciclos, limites):
    """Largo (1, 2, ...) de cada ciclo según el segundo en que empieza; 0 = fuera de la prueba."""
    t = ciclos.t_inicio_s.to_numpy()
    largo = np.zeros(len(t), int)
    for k in range(len(limites) - 1):
        largo[(t >= limites[k]) & (t < limites[k + 1])] = k + 1
    return largo


def mann_whitney(a, b):
    """p-valor bilateral de Mann-Whitney (scipy si está; si no, None)."""
    a, b = pd.Series(a).dropna(), pd.Series(b).dropna()
    if len(a) < 3 or len(b) < 3:
        return None
    try:
        from scipy.stats import mannwhitneyu
        return round(float(mannwhitneyu(a, b, alternative='two-sided').pvalue), 3)
    except Exception:
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('resultados', help='carpeta con variables_por_ciclo.csv (salida de analizar.py)')
    ap.add_argument('--pasos', type=float, nargs='+', required=True,
                    help='segundo del vídeo en que toca la pared al final de cada largo')
    ap.add_argument('--salida', type=float, default=0.0, help='segundo de la salida (por defecto 0)')
    ap.add_argument('--base-largos', type=int, default=2, help='largos que forman la fase fresca (por defecto 2)')
    ap.add_argument('--metros-largo', type=float, default=25.0)
    ap.add_argument('--nadador', default=None)
    a = ap.parse_args(argv)

    carpeta = Path(a.resultados)
    ciclos = pd.read_csv(carpeta / 'variables_por_ciclo.csv')
    nadador = a.nadador or carpeta.name
    limites = [a.salida] + list(a.pasos)
    if any(b <= c for c, b in zip(limites, limites[1:])):
        sys.exit('Los tiempos de paso deben ir en orden creciente.')
    out = carpeta / 'por_largos'
    out.mkdir(exist_ok=True)

    ciclos['largo'] = asignar_largos(ciclos, limites)
    ciclos = ciclos[ciclos.largo > 0].reset_index(drop=True)
    n_largos = len(limites) - 1
    lineas = [f'{nadador}: {n_largos} largos de {a.metros_largo:g} m; fase fresca = largos 1-{a.base_largos}.', '']

    # 1) Velocidad por largo: solo depende de los tiempos de paso
    filas = []
    for k in range(1, n_largos + 1):
        dur = limites[k] - limites[k - 1]
        c = ciclos[ciclos.largo == k]
        v = a.metros_largo / dur
        sr = c.SR_ciclos_min.median() if len(c) else np.nan
        filas.append(dict(largo=k, desde_s=limites[k - 1], hasta_s=limites[k], tiempo_s=round(dur, 2),
                          velocidad_m_s=round(v, 3), ciclos_medidos=len(c), SR_mediana=round(sr, 1) if len(c) else None,
                          distancia_por_ciclo_m=round(v * 60 / sr, 2) if len(c) else None))
    largos = pd.DataFrame(filas)
    largos.to_csv(out / 'largos.csv', index=False)
    lineas += ['Velocidad por largo (tiempo de paso, sin pose):', largos.to_string(index=False), '',
               'Nota: el largo 1 incluye la salida y el 4 la llegada; los demás, un viraje. La distancia por ciclo '
               'usa la frecuencia de los ciclos medidos en ese largo.', '']

    # 2) Variables por largo y comparación fresco (1-base) frente al resto
    vars_ok = [v for v in VARIABLES if v in ciclos and ciclos[v].notna().mean() >= 0.6]
    por_largo = ciclos.groupby('largo')[vars_ok].median().round(2)
    por_largo.insert(0, 'ciclos', ciclos.groupby('largo').size())
    por_largo.to_csv(out / 'variables_por_largo.csv')
    fresco, resto = ciclos[ciclos.largo <= a.base_largos], ciclos[ciclos.largo > a.base_largos]
    comp = []
    for v in vars_ok:
        f, r = fresco[v].median(), resto[v].median()
        comp.append(dict(variable=fatiga.NOMBRES.get(v, v), fresco=round(f, 2), despues=round(r, 2),
                         cambio_pct=round(100 * (r - f) / abs(f), 1) if f else None,
                         p_mann_whitney=mann_whitney(fresco[v], resto[v])))
    comp = pd.DataFrame(comp)
    comp.to_csv(out / 'comparacion.csv', index=False)
    lineas += [f'Variables: mediana en los largos 1-{a.base_largos} ({len(fresco)} ciclos) frente a los largos '
               f'{a.base_largos + 1}-{n_largos} ({len(resto)} ciclos):', comp.to_string(index=False), '',
               'p < 0,05 indica una diferencia poco probable por azar; con tan pocos ciclos, tómalo como orientativo.', '']

    # 3) Detector de fatiga con la fase base = largos frescos
    n_base = len(fresco)
    if n_base < 5 or len(resto) < 3:
        lineas.append(f'Detector: hacen falta al menos 5 ciclos frescos y 3 después (hay {n_base} y {len(resto)}).')
        res = None
    else:
        res = fatiga.analizar_fatiga(ciclos, frac_base=0.0, min_base=n_base)
        lineas += fatiga.explicar(ciclos, res, nadador)
        if 'anom' in res:
            sobre = (res['anom'][n_base:] > res['umbral'])
            lineas += ['', f'Ciclos por encima del umbral (p95 de los largos frescos) después de la fase fresca: '
                       f'{int(sobre.sum())} de {len(sobre)} ({100 * sobre.mean():.0f} %); en la fase fresca, por '
                       f'construcción, alrededor del 5 %.',
                       f'Anomalía mediana: frescos {np.median(res["anom"][:n_base]):.3f} · después '
                       f'{np.median(res["anom"][n_base:]):.3f} · p Mann-Whitney '
                       f'{mann_whitney(res["anom"][:n_base], res["anom"][n_base:])}']
            if res['inicio'] is None:
                imp = pd.DataFrame(res['shap'], columns=res['feats']).iloc[n_base:].mean().sort_values(ascending=False)
                lineas.append('Variables que más alejan del estado fresco en los largos siguientes (SHAP medio): ' +
                              ', '.join(f'{fatiga.NOMBRES.get(f, f)} {imp[f]:+.3f}' for f in imp.index[:3]))
            ciclos['anomalia_por_largos'] = res['anom']
            ciclos.to_csv(out / 'variables_por_ciclo_largos.csv', index=False)

    grafica(ciclos, largos, limites, res, a.base_largos, out / 'fig_largos.png', nadador)
    texto = '\n'.join(lineas)
    (out / 'informe_largos.txt').write_text(texto + '\n', encoding='utf-8')
    print(texto)
    print(f'\nResultados en {out}')
    return 0


def grafica(ciclos, largos, limites, res, base_largos, ruta, nadador):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(3, 1, figsize=(10, 8), sharex=False)
    x = np.arange(1, len(largos) + 1)
    ax[0].bar(x, largos.velocidad_m_s, color=['#2a78d6' if k <= base_largos else '#eb6834' for k in x])
    ax[0].set_xticks(x, [f'Largo {k}' for k in x])
    ax[0].set_ylabel('velocidad (m/s)')
    ax[0].set_title(f'{nadador}: velocidad por largo (tiempos de paso)')
    for xi, v in zip(x, largos.velocidad_m_s):
        ax[0].text(xi, v, f'{v:.2f}', ha='center', va='bottom')
    for k, a_ in enumerate(ax[1:]):
        for lim in limites[1:-1]:
            a_.axvline(lim, color='grey', lw=1, ls=':')
        a_.axvspan(limites[0], limites[base_largos], color='green', alpha=.08, label='largos frescos')
    ax[1].plot(ciclos.t_inicio_s, ciclos.SR_ciclos_min, 'o-', color='#2a78d6')
    ax[1].set_ylabel('ciclos/min')
    ax[1].set_title('Frecuencia de ciclo')
    if res is not None and 'anom' in res:
        ax[2].plot(ciclos.t_inicio_s, res['anom'], 'o-', color='#eb6834', label='anomalía por ciclo')
        ax[2].axhline(res['umbral'], color='k', ls='--', lw=1, label='umbral (p95 largos frescos)')
        if res['inicio'] is not None:
            ax[2].axvline(res['t_inicio'], color='red', lw=2, label=f'inicio fatiga ({res["t_inicio"]:.1f} s)')
        ax[2].legend(loc='upper left', fontsize=8)
    ax[2].set_ylabel('anomalía')
    ax[2].set_xlabel('segundo del vídeo')
    ax[2].set_title('Anomalía respecto a los largos frescos')
    fig.tight_layout()
    fig.savefig(ruta, dpi=130)
    plt.close(fig)


if __name__ == '__main__':
    raise SystemExit(main())
