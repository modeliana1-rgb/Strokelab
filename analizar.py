"""StrokeLab · análisis completo de un vídeo de nado en CPU (local).

Ejemplos (PowerShell, desde la carpeta del proyecto):
  python analizar.py "C:\\Users\\user\\StrokeLab\\videos\\GX011615.MP4" --nadador "Nadador A"
  python analizar.py VIDEO.MP4 --comparativa              # además compara modelos de pose en CPU
  python analizar.py VIDEO.MP4 --desde-keypoints           # reutiliza la pose ya extraída (rápido)

Salida en resultados/<nombre del vídeo>/: keypoints, CSV por fotograma y por ciclo, resumen JSON, figuras y vídeo anotado.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from strokelab import fatiga, medidas, pose, video

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
    ap.add_argument('--modelo', default='yolov8n-pose',
                    help='yolov8n-pose (defecto), yolo11n-pose, yolov8s-pose, movenet_lightning, movenet_thunder, mediapipe')
    ap.add_argument('--cada', type=int, default=2, help='analizar 1 de cada N fotogramas (2 = el doble de rápido)')
    ap.add_argument('--sin-3d', action='store_true', help='no usar MotionBERT (solo 2D)')
    ap.add_argument('--motionbert', help='ruta a best_epoch.bin de MotionBERT-Lite')
    ap.add_argument('--metros-encuadre', type=float, help='metros de piscina de borde a borde (solo cámara fija)')
    ap.add_argument('--comparativa', action='store_true', help='comparar modelos de pose en CPU antes del análisis')
    ap.add_argument('--desde-keypoints', action='store_true', help='reutilizar keypoints_raw.npz de la carpeta de salida')
    ap.add_argument('--formato', choices=['mp4', 'avi'], default='mp4', help='avi (MJPG) si el mp4 no se abre en tu equipo')
    ap.add_argument('--sin-video', action='store_true', help='no generar el vídeo anotado')
    a = ap.parse_args(argv)

    vid = Path(a.video)
    out = Path(a.salida) if a.salida else Path('resultados') / vid.stem
    out.mkdir(parents=True, exist_ok=True)
    t_total = time.time()
    print(f'StrokeLab · {vid.name} -> {out}')

    if a.comparativa:
        print('\n[0] Comparativa de modelos de pose en CPU (15 tramos de 10 fotogramas repartidos por el vídeo)')
        tabla = pose.comparar_modelos(vid, MODELOS_COMPARATIVA)
        tabla.to_csv(out / 'comparativa_modelos_cpu.csv', index=False)
        print(tabla.to_string(index=False))

    npz = out / 'keypoints_raw.npz'
    if a.desde_keypoints and npz.exists():
        d = np.load(npz)
        kps, conf, fps, W, H = d['kps'], d['conf'], float(d['fps']), int(d['w']), int(d['h'])
        print(f'\n[1] Pose 2D cargada de {npz.name}')
    else:
        print(f'\n[1] Pose 2D con {a.modelo} (1 de cada {a.cada} fotogramas)')
        t0 = time.time()
        kps, conf, fps, W, H = pose.extraer_keypoints(vid, a.modelo, cada=a.cada)
        np.savez(npz, kps=kps, conf=conf, fps=fps, w=W, h=H, modelo=a.modelo, cada=a.cada)
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
            modelo3d = lift3d.cargar_modelo(ck)
            t0 = time.time()
            k3d = lift3d.elevar_3d(k2d, conf_para_3d(conf, k2d, fps), modelo3d)
            np.save(out / 'keypoints_3d.npy', k3d)
            print(f'    OK en {time.time() - t0:.0f} s ({ck})')
        except Exception as e:
            print(f'    AVISO: sin 3D, se continúa en 2D. {type(e).__name__}: {e}')

    print('\n[4] Medidas por fotograma y ciclos de brazada')
    fr = medidas.medidas_por_fotograma(k2d, fps, k3d)
    fr.to_csv(out / 'medidas_por_fotograma.csv', index=False)
    brazo, sig, picos = medidas.detectar_ciclos(fr, fps)
    ciclos = medidas.variables_por_ciclo(fr, fps, brazo, picos, a.metros_encuadre, W)
    print(f'    ángulos en {"3D" if k3d is not None else "2D"} · tronco implausible descartado: '
          f'{fr.attrs["pct_tronco_descartado"]:.1f}% · nadador analizable {np.mean(~np.isnan(sig)) * len(sig) / fps:.1f} s '
          f'de {len(sig) / fps:.1f} s · entradas de mano {len(picos)} · ciclos válidos {len(ciclos)}')
    _grafica_ciclos(sig, picos, fps, out)

    print('\n[5] Fatiga (Isolation Forest + PELT + SHAP)')
    res = fatiga.analizar_fatiga(ciclos) if len(ciclos) else {'aviso': 'no hay ciclos válidos', 'inicio': None, 't_inicio': None, 'cambio_pelt': [], 'feats': []}
    if 'anom' in res:
        ciclos['anomalia'] = res['anom']
        ciclos['estado'] = ['fatigado' if res['inicio'] is not None and i >= res['inicio'] else 'fresco' for i in range(len(ciclos))]
        pd.DataFrame(res['shap'], columns=res['feats']).to_csv(out / 'shap_por_ciclo.csv', index=False)
        fatiga.graficas(ciclos, res, a.nadador, out)
    texto = fatiga.explicar(ciclos, res, a.nadador)
    print('    ' + '\n    '.join(texto))
    ciclos.to_csv(out / 'variables_por_ciclo.csv', index=False)
    if len(ciclos):
        print('\n    Medias por ciclo:')
        print(ciclos.drop(columns=['ciclo', 't_inicio_s', 'estado'], errors='ignore').mean().round(2).to_string())

    resumen = dict(video=vid.name, nadador=a.nadador, modelo_pose=a.modelo, cada=a.cada, angulos_3d=k3d is not None,
                   fps=fps, resolucion=f'{W}x{H}', duracion_s=round(len(kps) / fps, 2), ciclos_validos=len(ciclos),
                   pct_tronco_descartado=round(fr.attrs['pct_tronco_descartado'], 1),
                   inicio_fatiga_ciclo=None if res.get('inicio') is None else int(ciclos.ciclo.iloc[res['inicio']]),
                   inicio_fatiga_s=res.get('t_inicio'), cambio_pelt=res.get('cambio_pelt', []),
                   variables_modelo=res.get('feats', []),
                   medias=ciclos.drop(columns=['ciclo', 't_inicio_s', 'estado'], errors='ignore').mean().round(3).to_dict() if len(ciclos) else {},
                   explicacion=texto)
    (out / 'resumen.json').write_text(json.dumps(resumen, ensure_ascii=False, indent=2, default=float), encoding='utf-8')

    if not a.sin_video:
        print('\n[6] Vídeo anotado')
        t0 = time.time()
        destino = out / f'video_anotado.{a.formato}'
        video.anotar(vid, destino, k2d, fr, ciclos, fps, a.nadador, a.formato)
        print(f'    {destino} ({time.time() - t0:.0f} s)')

    print(f'\nListo en {time.time() - t_total:.0f} s. Resultados en: {out.resolve()}')


def _grafica_ciclos(sig, picos, fps, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    t = np.arange(len(sig)) / fps
    plt.figure(figsize=(14, 3)); plt.plot(t, sig, lw=1); plt.plot(t[picos], sig[picos], 'rv')
    plt.xlabel('tiempo (s)'); plt.ylabel('muñeca sobre eje (troncos)'); plt.title('Detección de ciclos de brazada')
    plt.tight_layout(); plt.savefig(out / 'fig_ciclos.png', dpi=150); plt.close()


if __name__ == '__main__':
    sys.exit(main())
