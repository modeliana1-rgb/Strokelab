"""StrokeLab · análisis completo de un vídeo de nado en CPU (local).

Ejemplos (PowerShell, desde la carpeta del proyecto):
  python analizar.py "C:\\Users\\user\\StrokeLab\\videos\\GX011615.MP4" --nadador "Nadador A"
  python analizar.py VIDEO.MP4 --comparativa              # además compara modelos de pose en CPU
  python analizar.py VIDEO.MP4 --desde-keypoints           # reutiliza la pose ya extraída (rápido)

Salida en resultados/<nombre del vídeo>/: keypoints, CSV por fotograma y por ciclo, resumen JSON, figuras y vídeo anotado.
"""
import os
# Windows: PyTorch y NumPy/scikit-learn traen cada uno su copia de OpenMP (libiomp5md.dll); sin esto el programa se
# cierra con "OMP: Error #15". Es el ajuste habitual para este conflicto y debe hacerse antes de importarlas.
os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from strokelab import VERSION_ANALISIS, estilo as estilos, fatiga, medidas, pose, video, vista as vistas

MODELOS_COMPARATIVA = ['yolov8n-pose', 'yolo11n-pose', 'yolov8s-pose', 'movenet_lightning', 'movenet_thunder', 'mediapipe']


def conf_para_3d(conf, k_limpio, fps, max_hueco_s=0.4):
    """Confianza para MotionBERT: se interpola en los fotogramas no analizados (--cada) y es 0 donde no hay punto."""
    c = pd.DataFrame(np.where(conf > 0, conf, np.nan))
    c = c.interpolate(limit=int(max_hueco_s * fps), limit_area='inside').fillna(0).to_numpy()
    return np.where(np.isnan(k_limpio[..., 0]), 0.0, c)


def main(argv=None):
    ap = argparse.ArgumentParser(description='StrokeLab: eficiencia y fatiga en natación a partir de vídeo (CPU).')
    ap.add_argument('video')
    ap.add_argument('--salida', help='carpeta de resultados (por defecto resultados/<vídeo>)')
    ap.add_argument('--nadador', default='Nadador')
    ap.add_argument('--estilo', default='crol', choices=list(medidas.ESTILOS) + ['auto'],
                    help='estilo de nado: fija cuántas brazadas forman un ciclo y el ritmo plausible. auto: lo estima '
                         'el sistema con reglas biomecánicas (brazos alternos o simultáneos y posición de la cabeza)')
    ap.add_argument('--modelo', default='yolov8n-pose',
                    help='yolov8n-pose (defecto), yolo11n-pose, yolov8s-pose, movenet_lightning, movenet_thunder, mediapipe')
    ap.add_argument('--imgsz', type=int, default=640, help='YOLO: lado de entrada de la red (1280 detecta mejor nadadores pequeños, ~4x más lento)')
    ap.add_argument('--conf-det', type=float, default=0.25, help='YOLO: confianza mínima para aceptar la detección del nadador')
    ap.add_argument('--cada', type=int, default=2, help='analizar 1 de cada N fotogramas (2 = el doble de rápido)')
    ap.add_argument('--sin-3d', action='store_true', help='no usar MotionBERT (solo 2D)')
    ap.add_argument('--motionbert', help='ruta a best_epoch.bin de MotionBERT-Lite')
    ap.add_argument('--metros-encuadre', type=float, help='metros de piscina de borde a borde (solo cámara fija)')
    ap.add_argument('--comparativa', action='store_true', help='comparar modelos de pose en CPU antes del análisis')
    ap.add_argument('--desde-keypoints', action='store_true', help='reutilizar keypoints_raw.npz de la carpeta de salida')
    ap.add_argument('--keypoints', help='reutilizar un keypoints_raw.npz de otra carpeta (p. ej. para comparar 2D y 3D)')
    ap.add_argument('--formato', choices=['mp4', 'avi'], default='mp4', help='avi (MJPG) si el mp4 no se abre en tu equipo')
    ap.add_argument('--sin-video', action='store_true', help='no generar el vídeo anotado')
    ap.add_argument('--girar', default='auto', choices=['auto', '0', '90', '-90'],
                    help='girar el fotograma para que el nadador quede de pie ante el modelo (auto: elige el mejor)')
    ap.add_argument('--vista', default='lateral', choices=['lateral', 'frontal', 'otra', 'auto'],
                    help='auto: el sistema decide por tramos (lateral o frontal) según la orientación del tronco. lateral: cámara de lado, ángulos en 2D (validado; el 3D falla en piernas bajo el agua). '
                         'frontal: el nadador viene hacia la cámara o se ve desde el borde; brazadas por el recorrido '
                         'de las muñecas y ángulos en 3D. otra (oblicua): brazadas como en lateral y ángulos en 3D')
    ap.add_argument('--dispositivo', default='auto', help="auto (GPU si hay, si no CPU), cpu o cuda:0")
    ap.add_argument('--panel', default='fatiga', choices=['fatiga', 'completo'],
                    help='panel del vídeo: solo fatiga (defecto) o también los ángulos articulares')
    a = ap.parse_args(argv)

    vid = Path(a.video)
    out = Path(a.salida) if a.salida else Path('resultados') / vid.stem
    out.mkdir(parents=True, exist_ok=True)
    pose.YOLO_IMGSZ, pose.YOLO_CONF = a.imgsz, a.conf_det
    pose.DISPOSITIVO = pose.elegir_dispositivo(a.dispositivo)
    t_total = time.time()
    print(f'StrokeLab · {vid.name} -> {out} · dispositivo {pose.DISPOSITIVO}')

    npz = out / 'keypoints_raw.npz'
    origen = Path(a.keypoints) if a.keypoints else (npz if a.desde_keypoints and npz.exists() else None)
    rot = 0
    if not origen:
        if a.girar == 'auto':
            print(f'\n[0] Orientación: nadador sin girar y girado ±90° con {a.modelo}')
            rot = pose.elegir_rotacion(vid, a.modelo)
            print(f'    elegido: {rot:+d}°')
        else:
            rot = int(a.girar)

    if a.comparativa:
        print(f'\n[0] Comparativa de modelos de pose en CPU (15 tramos de 10 fotogramas; giro {rot:+d}°)')
        tabla = pose.comparar_modelos(vid, MODELOS_COMPARATIVA, rot=rot)
        tabla.to_csv(out / 'comparativa_modelos_cpu.csv', index=False)
        print(tabla.to_string(index=False))

    if origen:
        with np.load(origen) as _npz:          # Windows: el archivo se cierra al terminar de leerlo
            d = dict(_npz)
        kps, conf, fps, W, H = d['kps'], d['conf'], float(d['fps']), int(d['w']), int(d['h'])
        rot = int(d['giro']) if 'giro' in d else 0
        ajustes = (int(d['imgsz']) if 'imgsz' in d else 640, float(d['conf_det']) if 'conf_det' in d else 0.25)
        if origen != npz:
            np.savez(npz, **{k: d[k] for k in d})
        print(f'\n[1] Pose 2D cargada de {origen}')
    else:
        print(f'\n[1] Pose 2D con {a.modelo} (1 de cada {a.cada} fotogramas, giro {rot:+d}°)')
        t0 = time.time()
        kps, conf, fps, W, H = pose.extraer_keypoints(vid, a.modelo, cada=a.cada, rot=rot)
        ajustes = (a.imgsz, a.conf_det)
        np.savez(npz, kps=kps, conf=conf, fps=fps, w=W, h=H, modelo=a.modelo, cada=a.cada, giro=rot, imgsz=a.imgsz, conf_det=a.conf_det)
        print(f'    {len(kps)} fotogramas, {W}x{H}, {fps:.2f} fps, en {time.time() - t0:.0f} s')
    analizados = conf.max(1) > 0
    print(f'    fotogramas analizados con >= 5 articulaciones fiables: '
          f'{100 * np.mean((conf[analizados] > 0.3).sum(1) >= 5):.1f}%')

    print('\n[2] Limpieza (confianza, huecos <= 0.4 s, suavizado)')
    k2d, validez = medidas.limpiar(kps, conf, fps)
    print('    % fotogramas válidos por articulación: ' + ', '.join(f'{n} {v:.0f}' for n, v in validez.items() if n[:3] != 'ojo' and n[:4] != 'orej'))

    k3d = None
    if not a.sin_3d:
        print('\n[3] Elevación a 3D con MotionBERT-Lite')
        try:
            from strokelab import lift3d
            ck = lift3d.localizar_checkpoint(a.motionbert)
            modelo3d = lift3d.cargar_modelo(ck, pose.DISPOSITIVO)
            t0 = time.time()
            k3d = lift3d.elevar_3d(k2d, conf_para_3d(conf, k2d, fps), modelo3d)
            np.save(out / 'keypoints_3d.npy', k3d)
            print(f'    OK en {time.time() - t0:.0f} s ({ck})')
        except Exception as e:
            print(f'    AVISO: sin 3D, se continúa en 2D. {type(e).__name__}: {e}')

    print('\n[4] Medidas por fotograma y ciclos de brazada')
    if a.vista == 'auto':
        tramos = vistas.detectar_vista(k2d, fps)
        print(f'    vista automática por tramos: {vistas.describir(tramos, fps)}')
    else:
        tramos = [(0, len(k2d), a.vista, None)]
    est = estilos.estimar_por_reglas(k2d, fps, tramos)
    estilo_indicado = a.estilo
    if a.estilo == 'auto':
        a.estilo = est['estilo_para_ciclos'] or 'crol'
        print(f'    estilo automático: {est["estilo"] or est["familia"] or "sin estimación"} (seguridad {est["seguridad"]}); '
              f'ciclos como {a.estilo}')
    else:
        print(f'    estilo indicado: {a.estilo} · estimado por el sistema: {est["estilo"] or est["familia"] or "sin estimación"} '
              f'(seguridad {est["seguridad"]})')
    familia_indicada = 'simultaneos' if a.estilo in ('mariposa', 'braza') else 'alternos'
    aviso_estilo = (est['familia'] is not None and estilo_indicado != 'auto' and est['familia'] != familia_indicada
                    and est['seguridad'] != 'baja')
    for r_ in est['razones']:
        print('      ' + r_)
    if aviso_estilo:
        print(f'    AVISO: el estilo indicado ({a.estilo}) no coincide con lo observado (brazos {est["familia"]}): revisar la lista')
    partes = [_analizar_tramo(k2d, k3d, fps, a, W, ini, fin, v) for ini, fin, v, _ in tramos]
    fr = pd.concat([p['fr'] for p in partes], ignore_index=True)
    fr['t'] = np.arange(len(fr)) / fps
    fr.attrs = {k: float(sum(p['fr'].attrs[k] * len(p['fr']) for p in partes) / len(fr))
                for k in ('pct_tronco_descartado', 'pct_tronco_girado')}
    fr.to_csv(out / 'medidas_por_fotograma.csv', index=False)
    sig = np.concatenate([p['sig'] for p in partes])
    picos = np.concatenate([np.asarray(p['picos'], int) + ini for p, (ini, *_) in zip(partes, tramos)]).astype(int)
    ciclos_ab = [(x + ini, y + ini) for p, (ini, *_) in zip(partes, tramos) for x, y in p['ciclos_ab']]
    ciclos = pd.concat([p['ciclos'] for p in partes if len(p['ciclos'])], ignore_index=True) if any(len(p['ciclos']) for p in partes) else partes[0]['ciclos']
    if len(ciclos):
        ciclos['ciclo'] = range(1, len(ciclos) + 1)
    usar_3d = any(p['usar_3d'] for p in partes)
    print(f'    tronco implausible descartado: {fr.attrs["pct_tronco_descartado"]:.1f}% (con tronco girado: '
          f'{fr.attrs["pct_tronco_girado"]:.1f}%) · nadador analizable {np.mean(~np.isnan(sig)) * len(sig) / fps:.1f} s '
          f'de {len(sig) / fps:.1f} s · brazadas {len(picos)} · ciclos válidos {len(ciclos)}')
    _grafica_ciclos(sig, picos, ciclos_ab, fps, out, medidas.ESTILOS[a.estilo]['brazadas_ciclo'])

    # La fatiga compara al nadador consigo mismo en la MISMA vista: las variables de frente y de lado no son
    # comparables. Si el vídeo mezcla vistas, el modelo se aplica a la vista con más ciclos.
    vista_principal = ciclos.vista.value_counts().idxmax() if len(ciclos) else tramos[0][2]
    ciclos_f = ciclos[ciclos.vista == vista_principal].reset_index(drop=True).copy() if len(ciclos) else ciclos
    if len(ciclos_f) < len(ciclos):
        print(f'    fatiga sobre los {len(ciclos_f)} ciclos en vista {vista_principal} (los otros {len(ciclos) - len(ciclos_f)} quedan en las tablas)')
    print('\n[5] Fatiga (Isolation Forest + PELT + SHAP)')
    res = fatiga.analizar_fatiga(ciclos_f) if len(ciclos_f) else {'aviso': 'no hay ciclos válidos', 'inicio': None, 't_inicio': None, 'cambio_pelt': [], 'feats': []}
    if 'anom' in res:
        ciclos_f['anomalia'] = res['anom']
        ciclos_f['estado'] = ['fatigado' if res['inicio'] is not None and i >= res['inicio'] else 'fresco' for i in range(len(ciclos_f))]
        pd.DataFrame(res['shap'], columns=res['feats']).to_csv(out / 'shap_por_ciclo.csv', index=False)
        fatiga.graficas(ciclos_f, res, a.nadador, out)
        ciclos = ciclos.merge(ciclos_f[['ciclo', 'anomalia', 'estado']], on='ciclo', how='left')
    texto = fatiga.explicar(ciclos_f, res, a.nadador)
    if aviso_estilo:
        texto.append(f'AVISO: el estilo indicado ({a.estilo}) no coincide con lo observado en el vídeo (brazos {est["familia"]}).')
    print('    ' + '\n    '.join(texto))
    ciclos.to_csv(out / 'variables_por_ciclo.csv', index=False)
    if len(ciclos):
        print('\n    Medias por ciclo:')
        print(ciclos.drop(columns=['ciclo', 't_inicio_s', 'estado', 'vista'], errors='ignore').mean().round(2).to_string())

    resumen = dict(version=VERSION_ANALISIS, video=vid.name, nadador=a.nadador, estilo=a.estilo, estilo_indicado=estilo_indicado,
                   estilo_estimado=est['estilo'], familia_estimada=est['familia'], seguridad_estilo=est['seguridad'],
                   razones_estilo=est['razones'], aviso_estilo=bool(aviso_estilo), imgsz=ajustes[0], conf_det=ajustes[1], modelo_pose=a.modelo, cada=a.cada, giro=rot, angulos_3d=bool(usar_3d), vista=vista_principal, vista_pedida=a.vista,
                   tramos_vista=[dict(inicio_s=round(x / fps, 1), fin_s=round(y / fps, 1), vista=v) for x, y, v, _ in tramos],
                   fps=fps, resolucion=f'{W}x{H}', duracion_s=round(len(kps) / fps, 2), ciclos_validos=len(ciclos),
                   pct_deteccion=round(float(100 * np.mean((conf[analizados] > 0.3).sum(1) >= 5)), 1),
                   s_analizable=round(float(np.mean(~np.isnan(sig)) * len(sig) / fps), 1),
                   SR_media=round(float(ciclos.SR_ciclos_min.mean()), 1) if len(ciclos) else None,
                   pct_tronco_descartado=round(fr.attrs['pct_tronco_descartado'], 1),
                   pct_tronco_girado=round(fr.attrs['pct_tronco_girado'], 1),
                   inicio_fatiga_ciclo=None if res.get('inicio') is None else int(ciclos_f.ciclo.iloc[res['inicio']]),
                   inicio_fatiga_s=res.get('t_inicio'), cambio_pelt=res.get('cambio_pelt', []),
                   variables_modelo=res.get('feats', []),
                   medias=ciclos.drop(columns=['ciclo', 't_inicio_s', 'estado', 'vista'], errors='ignore').mean().round(3).to_dict() if len(ciclos) else {},
                   explicacion=texto)
    (out / 'resumen.json').write_text(json.dumps(resumen, ensure_ascii=False, indent=2, default=float), encoding='utf-8')

    if not a.sin_video:
        print('\n[6] Vídeo anotado')
        t0 = time.time()
        destino = out / f'video_anotado.{a.formato}'
        video.anotar(vid, destino, k2d, fr, ciclos_f, fps, a.nadador, a.formato, res=res, panel=a.panel,
                     info=f'{a.estilo} · vista {vista_principal}')
        print(f'    {destino} ({time.time() - t0:.0f} s)')

    print(f'\nListo en {time.time() - t_total:.0f} s. Resultados en: {out.resolve()}')


def _analizar_tramo(k2d, k3d, fps, a, W, ini, fin, vista):
    """Medidas, brazadas y variables por ciclo de un tramo del vídeo con una sola vista."""
    k2 = k2d[ini:fin]
    k3 = k3d[ini:fin] if k3d is not None else None
    usar_3d = k3 is not None and vista != 'lateral'
    fr = medidas.medidas_por_fotograma(k2, fps, k3 if usar_3d else None, vista)
    if k3 is not None and not usar_3d:        # el 3D se guarda aparte para comparar (columnas *_3d)
        f3 = medidas.medidas_por_fotograma(k2, fps, k3)
        for c in ['codo_I', 'codo_D', 'hombro_I', 'hombro_D', 'cadera_I', 'cadera_D', 'rodilla_I', 'rodilla_D']:
            fr[c + '_3d'] = f3[c]
    fr['vista'] = vista
    sig, picos, ciclos_ab, T_br = medidas.detectar_ciclos(fr, fps, a.estilo, vista)
    ciclos = medidas.variables_por_ciclo(fr, fps, ciclos_ab, a.metros_encuadre, W, a.estilo, vista)
    if vista == 'frontal' and not usar_3d and len(ciclos):  # de frente, los ángulos 2D son proyecciones sin sentido
        angulos = [c for c in ciclos if c.split('_')[0] in ('codo', 'hombro', 'cadera', 'rodilla')]
        ciclos[angulos] = np.nan
        print('    vista frontal sin 3D: los ángulos articulares no se calculan (hacen falta los de MotionBERT)')
    if len(ciclos):
        ciclos['t_inicio_s'] = (ciclos.t_inicio_s + ini / fps).round(2)
        ciclos['vista'] = vista
    print(f'    {vista} {ini / fps:.0f}-{fin / fps:.0f} s: ángulos en {"3D" if usar_3d else "2D"} · brazadas {len(picos)} '
          f'(ritmo típico {T_br or 0:.2f} s) · ciclos válidos {len(ciclos)}')
    return dict(fr=fr, sig=np.asarray(sig, float), picos=picos, ciclos_ab=ciclos_ab, ciclos=ciclos, usar_3d=usar_3d, T_br=T_br)


def _grafica_ciclos(sig, picos, ciclos_ab, fps, out, brazadas_ciclo=2):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    t = np.arange(len(sig)) / fps
    plt.figure(figsize=(14, 3)); plt.plot(t, sig, lw=1, label='profundidad de la mano más profunda (troncos)')
    plt.plot(t[picos], sig[picos], 'rv', label='brazada')
    for a_, b_ in ciclos_ab:
        plt.axvspan(t[a_], t[b_ - 1] if b_ - 1 < len(t) else t[-1], color='green', alpha=0.08)
    plt.xlabel('tiempo (s)'); plt.title(f'Brazadas y ciclos (sombreado: 1 ciclo = {brazadas_ciclo} brazada{"s" if brazadas_ciclo > 1 else ""})'); plt.legend(loc='upper right')
    plt.tight_layout(); plt.savefig(out / 'fig_ciclos.png', dpi=150); plt.close()


if __name__ == '__main__':
    sys.exit(main())
