"""Vertical 2 · Fatiga: en qué ciclo aparece y por qué (Isolation Forest + PELT + SHAP)."""
import numpy as np
import pandas as pd

NOMBRES = {
    'SR_ciclos_min': 'Frecuencia de ciclo (ciclos/min)',
    'codo_min_I': 'Flexión codo izq. en agarre (°)', 'codo_min_D': 'Flexión codo dcho. en agarre (°)',
    'hombro_max_I': 'Apertura hombro izq. (°)', 'hombro_max_D': 'Apertura hombro dcho. (°)',
    'cadera_media_I': 'Ángulo cadera izq. (°)', 'cadera_media_D': 'Ángulo cadera dcha. (°)',
    'rodilla_min_I': 'Flexión rodilla izq. (°)', 'rodilla_min_D': 'Flexión rodilla dcha. (°)',
    'alcance_I': 'Alcance brazo izq. (troncos)', 'alcance_D': 'Alcance brazo dcho. (troncos)',
    'asimetria_brazos_pct': 'Asimetría de brazos (%)', 'inclinacion_tronco': 'Inclinación del tronco (°)',
    'amplitud_patada': 'Amplitud de patada (troncos)', 'patadas_por_ciclo': 'Patadas por ciclo',
    'DPS_m': 'Distancia por ciclo (m)',
}
# No se usan a la vez velocidad, DPS y SR (v = SR * DPS / 60): SHAP repartiría la importancia entre ellas.
CANDIDATAS = ['SR_ciclos_min', 'codo_min_I', 'codo_min_D', 'hombro_max_I', 'hombro_max_D', 'cadera_media_I',
              'cadera_media_D', 'rodilla_min_I', 'rodilla_min_D', 'alcance_I', 'alcance_D', 'asimetria_brazos_pct',
              'inclinacion_tronco', 'amplitud_patada', 'patadas_por_ciclo', 'DPS_m']


def cambios_pelt(serie, pen=None, min_seg=2):
    """Puntos de cambio en la media con PELT (Killick et al., 2012), coste L2, sobre la serie estandarizada.

    Implementación propia (sin dependencias compiladas). pen por defecto = 2·ln(n) (criterio tipo BIC).
    Devuelve los índices donde empieza cada segmento nuevo.
    """
    x = np.asarray(serie, float)
    n = len(x)
    if n < 2 * min_seg:
        return []
    x = (x - x.mean()) / (x.std() or 1.0)
    pen = 2 * np.log(n) if pen is None else pen
    cs, cs2 = np.r_[0, np.cumsum(x)], np.r_[0, np.cumsum(x * x)]
    coste = lambda a, b: (cs2[b] - cs2[a]) - (cs[b] - cs[a]) ** 2 / (b - a)
    F = np.full(n + 1, np.inf)
    F[0] = -pen
    previo = np.zeros(n + 1, int)
    candidatos = [0]
    for t in range(min_seg, n + 1):
        validos = [s for s in candidatos if t - s >= min_seg]
        vals = [F[s] + coste(s, t) + pen for s in validos]
        i = int(np.argmin(vals))
        F[t], previo[t] = vals[i], validos[i]
        # poda de PELT: se descartan los inicios que ya no pueden ser óptimos
        candidatos = [s for s in candidatos if t - s < min_seg or F[s] + coste(s, t) <= F[t]] + [t - min_seg + 1]
    cambios, t = [], n
    while t > 0:
        t = previo[t]
        if t > 0:
            cambios.append(int(t))
    return sorted(cambios)


def analizar_fatiga(ciclos, frac_base=0.30, min_base=5):
    """Devuelve un dict con el inicio de la fatiga, la serie de anomalía, los SHAP y la explicación."""
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    import shap

    feats = [f for f in CANDIDATAS if f in ciclos and ciclos[f].notna().mean() >= 0.6]
    X = ciclos[feats].copy()
    X = X.fillna(X.median())
    n_base = max(min_base, int(frac_base * len(X)))
    res = dict(feats=feats, n_base=n_base, inicio=None, t_inicio=None, cambio_pelt=[], X=X)
    if len(X) < n_base + 3:
        res['aviso'] = f'Solo {len(X)} ciclos: hacen falta al menos {n_base + 3} (mejor >= 12) para analizar fatiga.'
        return res

    scaler = StandardScaler().fit(X.iloc[:n_base])
    Xs = pd.DataFrame(np.nan_to_num(scaler.transform(X)), columns=feats)
    iso = IsolationForest(n_estimators=500, random_state=42).fit(Xs.iloc[:n_base])
    anom = -iso.score_samples(Xs)                         # mayor = más alejado del estado fresco
    umbral = float(np.percentile(anom[:n_base], 95))
    suav = pd.Series(anom).rolling(3, min_periods=1).mean().to_numpy()
    inicio = next((i for i in range(n_base, len(suav) - 2) if (suav[i:i + 3] > umbral).all()), None)
    cambio = [c for c in cambios_pelt(anom) if c >= n_base]

    expl = shap.TreeExplainer(iso)
    sv = -expl.shap_values(Xs)                            # positivo = empuja hacia "fatigado"
    res.update(anom=anom, suav=suav, umbral=umbral, inicio=inicio, cambio_pelt=cambio, shap=sv,
               base_shap=float(-np.ravel(expl.expected_value)[0]),
               signo_ok=float(np.corrcoef(sv.sum(1), anom)[0, 1]))
    if inicio is not None:
        res['t_inicio'] = float(ciclos.t_inicio_s.iloc[inicio])
    return res


def explicar(ciclos, res, nadador):
    if 'aviso' in res:
        return [f'{nadador}: {res["aviso"]}']
    inicio = res['inicio']
    if inicio is None:
        return [f'{nadador}: no se detecta fatiga sostenida en los {len(ciclos)} ciclos analizados.']
    X, n_base, feats = res['X'], res['n_base'], res['feats']
    imp = pd.DataFrame(res['shap'], columns=feats).iloc[inicio:].mean().sort_values(ascending=False)
    lineas = [f'{nadador}: la fatiga aparece en el ciclo {int(ciclos.ciclo.iloc[inicio])} '
              f'(t = {res["t_inicio"]:.1f} s, {100 * inicio / len(ciclos):.0f}% del recorrido).',
              'Principales causas (contribución SHAP media tras el inicio):']
    for f in imp.index[:4]:
        if imp[f] <= 0:
            continue
        b, p = X[f].iloc[:n_base].mean(), X[f].iloc[inicio:].mean()
        lineas.append(f'  - {NOMBRES[f]}: {b:.2f} -> {p:.2f} ({100 * (p - b) / abs(b):+.0f}%)  [SHAP {imp[f]:+.3f}]')
    return lineas


def graficas(ciclos, res, nadador, carpeta):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import shap
    if 'anom' not in res:
        return
    t = ciclos.t_inicio_s
    fig, ax = plt.subplots(2, 1, figsize=(14, 7), sharex=True)
    ax[0].plot(t, res['anom'], 'o-', label='anomalía por ciclo')
    ax[0].plot(t, res['suav'], lw=3, alpha=.6, label='media móvil 3')
    ax[0].axhline(res['umbral'], ls='--', c='gray', label='umbral (p95 fase fresca)')
    ax[0].axvspan(t.iloc[0], t.iloc[res['n_base'] - 1], color='green', alpha=.08, label='fase base (fresco)')
    if res['t_inicio'] is not None:
        ax[0].axvline(res['t_inicio'], c='red', lw=2, label=f'inicio fatiga ({res["t_inicio"]:.1f} s)')
        ax[1].axvline(res['t_inicio'], c='red', lw=2)
    ax[0].legend(loc='upper left'); ax[0].set_ylabel('puntuación de anomalía'); ax[0].set_title(f'{nadador}: evolución de la fatiga')
    ax[1].plot(t, ciclos.SR_ciclos_min, 'o-', label='SR (ciclos/min)')
    ax2 = ax[1].twinx()
    ax2.plot(t, ciclos[['codo_min_I', 'codo_min_D']].mean(1), 's-', c='C1', label='flexión de codo (°)')
    ax[1].set_xlabel('tiempo (s)'); ax[1].set_ylabel('SR'); ax2.set_ylabel('codo (°)')
    ax[1].legend(loc='upper left'); ax2.legend(loc='upper right')
    plt.tight_layout(); plt.savefig(carpeta / 'fig_fatiga_timeline.png', dpi=150); plt.close()

    Xn = res['X'].rename(columns=NOMBRES)
    plt.figure(); shap.summary_plot(res['shap'], Xn, show=False); plt.title('SHAP: contribución a la fatiga')
    plt.tight_layout(); plt.savefig(carpeta / 'fig_shap_summary.png', dpi=150, bbox_inches='tight'); plt.close()
    if res['inicio'] is not None:
        i = res['inicio']
        e = shap.Explanation(values=res['shap'][i], base_values=res['base_shap'], data=res['X'].iloc[i].values,
                             feature_names=[NOMBRES[f] for f in res['feats']])
        plt.figure(); shap.plots.waterfall(e, show=False)
        plt.title(f'Por qué el ciclo {int(ciclos.ciclo.iloc[i])} ya es fatiga')
        plt.tight_layout(); plt.savefig(carpeta / 'fig_shap_waterfall_inicio.png', dpi=150, bbox_inches='tight'); plt.close()
