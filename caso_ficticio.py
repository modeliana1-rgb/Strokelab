"""StrokeLab · CASO FICTICIO de demostración: un nadador simulado del que se conoce la verdad.

Muestra todo lo que hace el sistema y mide su error frente a la verdad:
  A) crol en vista lateral, cámara fija que cubre los 25 m (velocidad, DPS e Índice de Brazada calibrados),
     2 minutos de nado con fatiga programada a partir de t = 70 s;
  B) el mismo nadador en vista frontal;
  C) clasificación del estilo con SHAP: 64 vídeos simulados (4 estilos x 2 vistas x 8 nadadores), validación
     agrupada por vídeo, y predicción del estilo de A y B, que no se usan para entrenar.
NO son datos reales: en la memoria se presenta como caso simulado.

Uso:  python caso_ficticio.py [--salida resultados/caso_ficticio] [--sin-video]
"""
import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')

import numpy as np
import pandas as pd

import analizar
from strokelab import estilo, fatiga, medidas, simulador

AZUL, GRIS, ROJO = '#2a78d6', '#898781', '#d03b3b'
T_FATIGA = 70.0


def caso(nombre, vista, out, con_video, seed):
    s = simulador.simular('crol', vista, dur=120, seed=seed, t_fatiga=T_FATIGA)
    d = out / nombre
    d.mkdir(parents=True, exist_ok=True)
    np.savez(d / 'keypoints_raw.npz', kps=s['kps'], conf=s['conf'], fps=s['fps'], w=s['W'], h=s['H'])
    s['verdad'].to_csv(d / 'verdad.csv', index=False)
    vid = d / 'nadador_simulado.mp4'
    if con_video:
        simulador.dibujar_video(vid, s)
    args = [str(vid), '--salida', str(d), '--desde-keypoints', '--sin-3d', '--nadador', 'Nadador ficticio',
            '--estilo', 'crol', '--vista', vista]
    if vista == 'lateral':
        args += ['--metros-encuadre', '25']
    if not con_video:
        args.append('--sin-video')
    analizar.main(args)
    ciclos = pd.read_csv(d / 'variables_por_ciclo.csv')
    res = json.loads((d / 'resumen.json').read_text(encoding='utf-8'))
    ver = s['verdad']
    i = (ciclos.t_inicio_s * s['fps']).round().astype(int).clip(0, len(ver) - 1)
    # verdad media de cada ciclo (del inicio al final del ciclo)
    fin = ((ciclos.t_inicio_s + ciclos.duracion_s) * s['fps']).round().astype(int).clip(0, len(ver) - 1)
    for col in ['SR_ciclos_min', 'velocidad_m_s', 'DPS_m']:
        ciclos[f'{col}_verdad'] = [ver[col].iloc[a:b + 1].mean() for a, b in zip(i, fin)]
    err = {}
    for col in ['SR_ciclos_min', 'velocidad_m_s', 'DPS_m']:
        if col in ciclos:
            e = 100 * (ciclos[col] - ciclos[f'{col}_verdad']).abs() / ciclos[f'{col}_verdad']
            err[col] = round(float(e.median()), 1)
    ciclos.to_csv(d / 'ciclos_con_verdad.csv', index=False)
    t10, t90 = (T_FATIGA + 5 * np.log(1 / 9), T_FATIGA + 5 * np.log(9))      # la fatiga programada pasa del 10 % al 90 %
    return dict(vista=vista, ciclos=len(ciclos), error_mediano_pct=err, inicio_fatiga_s=res.get('inicio_fatiga_s'),
                transicion_programada_s=[round(t10, 1), round(t90, 1)], explicacion=res.get('explicacion')), ciclos


def figura_lateral(ciclos, inicio, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': True,
                         'grid.color': '#e8e6df', 'axes.axisbelow': True})
    fig, axs = plt.subplots(3, 1, figsize=(10, 7), sharex=True, dpi=150)
    for ax, col, nombre in zip(axs, ['velocidad_m_s', 'SR_ciclos_min', 'DPS_m'],
                               ['Velocidad (m/s)', 'Frecuencia de ciclo (ciclos/min)', 'Distancia por ciclo (m)']):
        ax.plot(ciclos.t_inicio_s, ciclos[f'{col}_verdad'], color=GRIS, lw=2, label='referencia (simulación)')
        ax.plot(ciclos.t_inicio_s, ciclos[col], 'o', ms=4, color=AZUL, label='estimación del sistema')
        ax.axvspan(T_FATIGA - 11, T_FATIGA + 11, color='#f4d9d9', alpha=0.5, lw=0)
        if inicio is not None:
            ax.axvline(inicio, color=ROJO, lw=1.5)
        ax.set_title(nombre, fontsize=9, loc='left')
    axs[0].legend(fontsize=8, frameon=False, loc='lower left')
    axs[0].text(T_FATIGA, axs[0].get_ylim()[1], ' fatiga programada', color=ROJO, fontsize=8, va='top', ha='center')
    if inicio is not None:
        axs[1].text(inicio, axs[1].get_ylim()[1], f' inicio detectado ({inicio:.1f} s)', color=ROJO, fontsize=8, va='top')
    axs[-1].set_xlabel('tiempo (s)')
    fig.suptitle('Datos sintéticos (crol, vista lateral): estimación del sistema frente a la referencia', fontsize=10, x=0.01, ha='left')
    fig.tight_layout()
    fig.savefig(out / 'fig_verdad_vs_sistema.png')
    plt.close(fig)


def clasificacion_estilo(out, A, B):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rng = np.random.default_rng(0)
    filas = []
    for e in estilo.ESTILOS:
        for vista in ('lateral', 'frontal'):
            for sd in range(8):
                s = simulador.simular(e, vista, dur=40, seed=1000 + 37 * sd + 7 * estilo.ESTILOS.index(e) + (vista == 'frontal'),
                                      t_fatiga=[None, 20.0][sd % 2], variacion=1.0, ruido_px=rng.uniform(1, 3),
                                      copia_brazos=rng.uniform(0, 0.9) if vista == 'lateral' else 0.0)
                k2d, _ = medidas.limpiar(s['kps'], s['conf'], s['fps'])
                r = estilo.rasgos_ventanas(k2d, s['fps'], vista)
                filas.append(r.assign(estilo=e, video=f'{e}_{vista}_{sd}'))
    datos = pd.concat(filas, ignore_index=True)
    ev = estilo.evaluar(datos)
    modelo = estilo.entrenar(datos, datos.estilo)
    imp = estilo.shap_por_estilo(modelo, datos)
    pred = {}
    for nombre, d, vista in (('A', A, 'lateral'), ('B', B, 'frontal')):
        z = np.load(d / 'keypoints_raw.npz')
        k2d, _ = medidas.limpiar(z['kps'], z['conf'], float(z['fps']))
        pred[nombre] = estilo.predecir(modelo, estilo.rasgos_ventanas(k2d, float(z['fps']), vista))
    ev['confusion'].to_csv(out / 'estilo_confusion.csv')
    imp.to_csv(out / 'estilo_shap.csv')

    fig, axs = plt.subplots(1, 2, figsize=(11, 4), dpi=150, gridspec_kw={'width_ratios': [1, 1.4]})
    c = ev['confusion'].to_numpy()
    axs[0].imshow(c, cmap='Blues')
    axs[0].grid(False)
    for (i, j), v in np.ndenumerate(c):
        axs[0].text(j, i, int(v), ha='center', va='center', color='white' if v > c.max() / 2 else '#0b0b0b')
    axs[0].set_xticks(range(4), estilo.ESTILOS, fontsize=8)
    axs[0].set_yticks(range(4), estilo.ESTILOS, fontsize=8)
    axs[0].set_xlabel('predicho'); axs[0].set_ylabel('real')
    axs[0].set_title(f'Vídeos bien clasificados: {ev["exactitud_video"]:.0%} (GroupKFold)', fontsize=9, loc='left')
    orden = imp.sum(1).sort_values().index
    izq = np.zeros(len(orden))
    for e, col in zip(imp.columns, ['#2a78d6', '#eb6834', '#1baf7a', '#eda100']):
        axs[1].barh([estilo.NOMBRES[r] for r in orden], imp.loc[orden, e], left=izq, color=col, label=e, height=0.65,
                    edgecolor='white', linewidth=1)
        izq += imp.loc[orden, e].to_numpy()
    axs[1].set_xlabel('|SHAP| medio')
    axs[1].set_title('Qué rasgo decide cada estilo (SHAP)', fontsize=9, loc='left')
    axs[1].legend(fontsize=8, frameon=False, loc='lower right')
    axs[1].tick_params(axis='y', labelsize=8)
    for s_ in ('top', 'right'):
        axs[1].spines[s_].set_visible(False)
    fig.tight_layout()
    fig.savefig(out / 'fig_estilo.png')
    plt.close(fig)
    return dict(videos=int(datos.video.nunique()), ventanas=len(datos), exactitud_ventana=round(ev['exactitud_ventana'], 3),
                exactitud_video=round(ev['exactitud_video'], 3), prediccion_A=pred['A'], prediccion_B=pred['B'],
                rasgo_principal={e: imp[e].idxmax() for e in imp.columns})


def main(argv=None):
    ap = argparse.ArgumentParser(description='Caso ficticio de demostración (nadador simulado).')
    ap.add_argument('--salida', default='resultados/caso_ficticio')
    ap.add_argument('--sin-video', action='store_true')
    a = ap.parse_args(argv)
    out = Path(a.salida)
    out.mkdir(parents=True, exist_ok=True)
    rA, cA = caso('A_lateral', 'lateral', out, not a.sin_video, seed=11)
    rB, _ = caso('B_frontal', 'frontal', out, not a.sin_video, seed=12)
    figura_lateral(cA, rA['inicio_fatiga_s'], out)
    rC = clasificacion_estilo(out, out / 'A_lateral', out / 'B_frontal')
    resumen = dict(aviso='CASO FICTICIO: nadador simulado, no son datos reales', A_lateral=rA, B_frontal=rB, estilo=rC)
    (out / 'resumen_caso.json').write_text(json.dumps(resumen, ensure_ascii=False, indent=2, default=float), encoding='utf-8')
    print(json.dumps(resumen, ensure_ascii=False, indent=2, default=float))
    return 0


if __name__ == '__main__':
    os.environ.setdefault('MPLBACKEND', 'Agg')
    sys.exit(main())
