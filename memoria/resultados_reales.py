"""Resultados reales para la memoria, leídos de una carpeta de resultados de lote.py (o de su para_claude.zip).

Así las tablas, cifras y figuras de datos reales salen siempre del último análisis, sin copiarlas a mano.
Uso desde generar_memoria.py:  R = resultados_reales.cargar(carpeta); resultados_reales.figuras(R, FIG)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ESTILO_ES = {'crol': 'crol', 'espalda': 'espalda', 'mariposa': 'mariposa', 'braza': 'braza'}
COL = {'crol': '#2a78d6', 'espalda': '#eda100', 'mariposa': '#eb6834', 'braza': '#1baf7a'}
LARGO_S = 120.0          # una secuencia de más de 2 min se trata como "secuencia larga" (análisis de fatiga)


def num(x, d=1):
    """Número con coma decimal."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return '—'
    return f'{x:.{d}f}'.replace('.', ',')


def cargar(carpeta):
    carpeta = Path(carpeta)
    L = pd.read_csv(carpeta / 'resumen_lote.csv', sep=';', encoding='utf-8-sig')
    L = L[L.estado == 'ok'].copy()
    L['clip'] = L.archivo.map(lambda a: Path(a).stem)
    filas, ciclos = [], []
    for r in L.itertuples():
        d = carpeta / r.clip
        js = json.loads((d / 'resumen.json').read_text(encoding='utf-8'))
        filas.append(dict(archivo=r.archivo, clip=r.clip, P=r.nadador, estilo=r.estilo, vista=js.get('vista', r.vista),
                          tramos=js.get('tramos_vista', []), dur=js['duracion_s'], det=js.get('pct_deteccion'),
                          anal=js.get('s_analizable'), ciclos=js.get('ciclos_validos', 0), SR=js.get('SR_media'),
                          estimado=js.get('estilo_estimado'), familia=js.get('familia_estimada'),
                          seguridad=js.get('seguridad_estilo'), aviso=bool(js.get('aviso_estilo')),
                          inicio=js.get('inicio_fatiga_s'), inicio_ciclo=js.get('inicio_fatiga_ciclo'),
                          explicacion=js.get('explicacion', []), imgsz=js.get('imgsz'), carpeta=d,
                          camara='móvil' if r.clip.upper().startswith('IMG') else 'GoPro' if r.clip.upper().startswith('GX') else 'otra'))
        try:
            c = pd.read_csv(d / 'variables_por_ciclo.csv')
        except (pd.errors.EmptyDataError, FileNotFoundError):
            c = pd.DataFrame()
        if len(c):
            if 'vista' not in c:
                c['vista'] = js.get('vista', r.vista)
            ciclos.append(c.assign(clip=r.clip, P=r.nadador, estilo=r.estilo))
    V = pd.DataFrame(filas).sort_values(['P', 'estilo', 'clip']).reset_index(drop=True)
    C = pd.concat(ciclos, ignore_index=True) if ciclos else pd.DataFrame()
    S = pd.read_csv(carpeta / 'resumen_sesiones.csv', sep=';', encoding='utf-8-sig') if (carpeta / 'resumen_sesiones.csv').exists() else pd.DataFrame()
    largo = V[V.dur >= LARGO_S].sort_values('dur', ascending=False)
    R = dict(carpeta=carpeta, V=V, C=C, S=S, largo=largo.iloc[0].to_dict() if len(largo) else None)
    R.update(n_videos=len(V), n_part=V.P.nunique(), participantes=sorted(V.P.unique()), estilos=sorted(V.estilo.unique()),
             dur=float(V.dur.sum()), anal=float(V.anal.fillna(0).sum()), ciclos=int(V.ciclos.fillna(0).sum()),
             imgsz=int(V.imgsz.dropna().mode().iloc[0]) if V.imgsz.notna().any() else None)
    R['pct'] = 100 * R['anal'] / R['dur'] if R['dur'] else 0
    # estilo estimado frente al indicado (solo vídeos con estimación)
    fam = lambda e: 'simultaneos' if e in ('mariposa', 'braza') else 'alternos'
    E = V[V.familia.notna()]
    R['estilo_n'] = len(E)
    R['familia_ok'] = int(sum(fam(a) == b for a, b in zip(E.estilo, E.familia)))
    R['estilo_ok'] = int(sum(a == b for a, b in zip(E.estilo, E.estimado)))
    R['estilo_sin_exacto'] = int(E.estimado.isna().sum() + (E.estimado == 'simultaneos').sum())
    return R


def tabla_por_video(R):
    filas = [['Secuencia', 'Part.', 'Estilo', 'Vista', 'Duración', 'Analizable', 'Ciclos', 'Frecuencia (ciclos/min)', 'Estilo estimado']]
    for v in R['V'].itertuples():
        est = v.estimado if isinstance(v.estimado, str) and v.estimado not in ('simultaneos', 'alternos') else (
            f'({v.familia})'.replace('simultaneos', 'simultáneos') if isinstance(v.familia, str) else '—')
        filas.append([v.clip, v.P, v.estilo.capitalize(), v.vista.capitalize(), f'{num(v.dur)} s', f'{num(v.anal)} s',
                      str(int(v.ciclos or 0)), num(v.SR), est])
    return filas


def tabla_cobertura(R):
    V = R['V']
    filas = [['Participante y estilo', 'Secuencias', 'Grabado', 'Analizable', 'Ciclos válidos']]
    for (p, e), g in V.groupby(['P', 'estilo']):
        filas.append([f'{p} · {e}', str(len(g)), f'{num(g.dur.sum())} s',
                      f'{num(g.anal.sum())} s ({100 * g.anal.sum() / g.dur.sum():.0f} %)', str(int(g.ciclos.sum()))])
    filas.append(['**Total**', f'**{R["n_videos"]}**', f'**{num(R["dur"])} s**', f'**{num(R["anal"])} s ({R["pct"]:.0f} %)**', f'**{R["ciclos"]}**'])
    return filas


def tabla_datos(R):
    V = R['V']
    filas = [['Participante', 'Estilos', 'Secuencias (GoPro / móvil / otra)', 'Duración grabada', 'Vistas']]
    for p, g in V.groupby('P'):
        cam = g.camara.value_counts()
        filas.append([p, ', '.join(sorted(g.estilo.unique())).capitalize(),
                      f'{cam.get("GoPro", 0)} / {cam.get("móvil", 0)} / {cam.get("otra", 0)}', f'{num(g.dur.sum())} s',
                      ' y '.join(sorted(g.vista.unique())).capitalize()])
    filas.append(['**Total**', f'**{len(R["estilos"])} estilos**', f'**{R["n_videos"]}**', f'**{num(R["dur"])} s**', ''])
    return filas


def perfil(R):
    """Media ± desviación de los ciclos laterales por participante y estilo."""
    C = R['C']
    if not len(C):
        return [], pd.DataFrame()
    C = C[C.vista == 'lateral'].copy()
    for c in ('codo_min', 'cadera_media', 'rodilla_min'):
        C[c] = C[[f'{c}_I', f'{c}_D']].mean(1)
    filas = [['Participante y estilo', 'Ciclos', 'Frecuencia (ciclos/min)', 'Codo (°)', 'Cadera (°)', 'Rodilla (°)', 'Inclinación (°)']]
    resumen = []
    for (p, e), g in C.groupby(['P', 'estilo']):
        ms = lambda c, d=0: f'{num(g[c].mean(), d)} ± {num(g[c].std(), d)}'
        filas.append([f'{p} · {e}', str(len(g)), ms('SR_ciclos_min', 1), ms('codo_min'), ms('cadera_media'), ms('rodilla_min'),
                      ms('inclinacion_tronco', 1)])
        resumen.append(dict(P=p, estilo=e, n=len(g), SR=g.SR_ciclos_min.mean(), SR_sd=g.SR_ciclos_min.std(),
                            codo=g.codo_min.mean(), incl=g.inclinacion_tronco.mean(), cadera=g.cadera_media.mean()))
    return filas, pd.DataFrame(resumen)


def tabla_sesiones(R):
    S = R['S']
    filas = [['Sesión', 'Secuencias', 'Ciclos', 'Inicio de la fatiga', 'Resultado']]
    for s in S[S.videos >= 2].itertuples():
        exp = str(s.explicacion)
        if 'Solo' in exp or 'hacen falta' in exp:
            res = 'Insuficiente (< 8 ciclos)'
        elif pd.notna(s.inicio_fatiga_ciclo):
            res = f'Fatiga desde el ciclo {int(s.inicio_fatiga_ciclo)}'
        else:
            res = 'Sin fatiga sostenida'
        filas.append([s.sesion.replace('_', ' · ').replace('gopro', 'GoPro').replace('movil', 'móvil'), str(s.videos), str(s.ciclos),
                      '—' if pd.isna(s.inicio_fatiga_ciclo) else f'ciclo {int(s.inicio_fatiga_ciclo)}', res])
    return filas


def figuras(R, FIG):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    plt.rcParams.update({'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': True, 'grid.color': '#e8e6df',
                         'axes.axisbelow': True, 'font.size': 9})
    V = R['V']
    fig, ax = plt.subplots(figsize=(10, max(3.5, 0.32 * len(V) + 1)), dpi=150)
    y = np.arange(len(V))
    ax.barh(y, V.dur, color='#dedbd2', height=0.7)
    ax.barh(y, V.anal.fillna(0), color=[COL[e] for e in V.estilo], height=0.7)
    for i, r in enumerate(V.itertuples()):
        ax.text(r.dur + V.dur.max() * 0.01, i, f'{int(r.ciclos or 0)} ciclos', va='center', fontsize=7.5, color='#444')
    ax.set_yticks(y, [f'{r.P} · {r.clip} · {r.vista[:3]}.' for r in V.itertuples()], fontsize=7.5)
    ax.invert_yaxis(); ax.set_xlabel('segundos')
    if V.dur.max() > 5 * V.dur.median():
        ax.set_xscale('symlog', linthresh=60); ax.set_xlabel('segundos (escala logarítmica a partir de 60 s)')
    ax.legend(handles=[Patch(color='#dedbd2', label='duración grabada')] + [Patch(color=COL[e], label=f'analizable · {e}') for e in R['estilos']],
              fontsize=7.5, frameon=False, loc='lower right')
    ax.set_title('Conjunto real: tiempo grabado, tiempo analizable y ciclos válidos por secuencia', loc='left', fontsize=9.5)
    fig.tight_layout(); fig.savefig(FIG / 'real_conjunto.png'); plt.close(fig)

    C = R['C']
    if len(C):
        C = C[C.vista == 'lateral'].copy()
        C['codo_min'] = C[['codo_min_I', 'codo_min_D']].mean(1)
        grupos = [g for g, _ in C.groupby(['P', 'estilo'])]
        fig, axs = plt.subplots(1, 3, figsize=(11, 3.8), dpi=150)
        for ax, col, nom in zip(axs, ['SR_ciclos_min', 'codo_min', 'inclinacion_tronco'],
                                ['Frecuencia de ciclo (ciclos/min)', 'Flexión del codo, media I-D (°)', 'Inclinación del tronco (°)']):
            vals = [C[(C.P == p) & (C.estilo == e)][col].dropna().to_numpy() for p, e in grupos]
            bp = ax.boxplot([v if len(v) else [np.nan] for v in vals], patch_artist=True, widths=0.6, showfliers=False)
            for b, (p, e) in zip(bp['boxes'], grupos):
                b.set_facecolor(COL[e]); b.set_alpha(0.35)
            for i, (v, (p, e)) in enumerate(zip(vals, grupos)):
                ax.plot(np.random.default_rng(i).normal(i + 1, 0.06, len(v)), v, 'o', ms=3, color=COL[e])
            ax.set_xticks(range(1, len(grupos) + 1), [f'{p}\n{e}' for p, e in grupos], fontsize=7.5)
            ax.set_title(nom, loc='left', fontsize=9)
        fig.tight_layout(); fig.savefig(FIG / 'real_participantes.png'); plt.close(fig)
    # figuras de fatiga: secuencia larga y sesiones con fatiga evaluada
    import shutil
    if R['largo'] is not None:
        for f in ('fig_fatiga_timeline.png', 'fig_shap_summary.png', 'fig_shap_waterfall_inicio.png', 'fig_ciclos.png'):
            if (R['largo']['carpeta'] / f).exists():
                shutil.copy(R['largo']['carpeta'] / f, FIG / f'real_largo_{f[4:]}')
    R['figs_sesion'] = []
    for s in R['S'].itertuples() if len(R['S']) else []:
        d = R['carpeta'] / f'sesion_{s.sesion}'
        if (d / 'fig_fatiga_timeline.png').exists() and s.ciclos >= 20:
            shutil.copy(d / 'fig_fatiga_timeline.png', FIG / f'real_sesion_{s.sesion}.png')
            R['figs_sesion'].append(s.sesion)
