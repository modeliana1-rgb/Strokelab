"""Prueba de extremo a extremo del programa local (analizar.py) con un nadador sintético que se fatiga.

Comprueba: detección del inicio de fatiga, medidas plausibles, vídeo anotado y el camino 3D (MotionBERT con
pesos aleatorios, solo para verificar que el flujo funciona; los valores 3D no se evalúan).

Uso:  python tests/test_local.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
import analizar  # noqa: E402


def nadador_sintetico(fps=30, dur=90, W=640, H=360, seed=0):
    """Nadador de crol visto de lado; fatiga progresiva centrada en t = 55 s."""
    rng = np.random.default_rng(seed)
    T = fps * dur
    t = np.arange(T) / fps
    fat = 1 / (1 + np.exp(-(t - 55) / 4))
    period = 1.35 - 0.25 * fat                    # ciclo más rápido
    phase = 2 * np.pi * np.cumsum(1 / period) / fps
    reach = 75 - 22 * fat                         # menos alcance
    elbow_bend = 25 + 20 * fat                    # más flexión de codo
    kps = np.zeros((T, 17, 2))
    conf = np.full((T, 17), 0.8)
    hip = np.c_[100 + t * 5 * (1 - 0.3 * fat), np.full(T, 200.)]
    hip[:, 1] += 5 * fat * np.sin(phase)
    sh = hip + np.c_[np.full(T, 80.), -4 - 6 * fat]
    for (S, E, Wr, Hp, K, A), off, asym in [((5, 7, 9, 11, 13, 15), np.pi, 1.0),
                                            ((6, 8, 10, 12, 14, 16), 0, 1.0 - 0.25 * fat)]:
        ph = phase + off
        r = reach * asym
        kps[:, S] = sh
        kps[:, Hp] = hip
        wr = sh + np.c_[r * np.cos(ph), 0.6 * r * np.sin(ph)]
        d = wr - sh
        n = np.c_[-d[:, 1], d[:, 0]] / np.linalg.norm(d, axis=1)[:, None]
        kps[:, E] = (sh + wr) / 2 + n * elbow_bend[:, None]
        kps[:, Wr] = wr
        kick = (12 - 5 * fat) * np.sin(6 * np.pi * np.cumsum(1 / period) / fps + off)
        kps[:, K] = hip + np.c_[np.full(T, -60.), kick / 2]
        kps[:, A] = hip + np.c_[np.full(T, -120.), kick]
    kps[:, 0] = sh + np.c_[np.full(T, 30.), np.zeros(T)]
    kps[:, 1:5] = kps[:, [0]]
    kps += rng.normal(0, 1.5, kps.shape)
    conf[rng.random((T, 17)) < 0.08] = 0.1
    conf[600:620] = 0                              # hueco de detección
    for t0 in (900, 1800, 2300):                   # errores típicos bajo el agua
        kps[t0:t0 + 4, [11, 12]] = kps[t0:t0 + 4, [5, 6]] + rng.normal(0, 2, (4, 2, 2))
        kps[t0 + 10:t0 + 13, [9, 10]] += rng.normal(0, 900, (3, 2, 2))
    conf[:150] = 0.05                              # tramo inicial sin nadador
    kps[conf == 0] = np.nan
    return kps, conf, fps, W, H


def main():
    tmp = Path(tempfile.mkdtemp())
    kps, conf, fps, W, H = nadador_sintetico()
    out = tmp / 'res'
    out.mkdir()
    np.savez(out / 'keypoints_raw.npz', kps=kps, conf=conf, fps=fps, w=W, h=H)
    vid = tmp / 'sintetico.mp4'
    vw = cv2.VideoWriter(str(vid), cv2.VideoWriter_fourcc(*'mp4v'), fps, (W, H))
    for _ in range(len(kps)):
        vw.write(np.full((H, W, 3), (120, 80, 20), np.uint8))
    vw.release()

    analizar.main([str(vid), '--salida', str(out), '--desde-keypoints', '--sin-3d', '--nadador', 'Sintético'])
    res = json.loads((out / 'resumen.json').read_text(encoding='utf-8'))
    assert res['inicio_fatiga_s'] is not None and 40 <= res['inicio_fatiga_s'] <= 60, res['inicio_fatiga_s']
    import pandas as pd
    cic = pd.read_csv(out / 'variables_por_ciclo.csv')
    assert cic[['alcance_I', 'alcance_D']].max().max() < 3, 'alcance imposible'
    assert cic[['codo_min_I', 'codo_min_D']].min().min() > 25, 'codo imposible'
    for col in ['hombro_max_I', 'cadera_media_D', 'rodilla_min_I', 'amplitud_patada', 'patadas_por_ciclo']:
        assert cic[col].notna().mean() > 0.8, f'{col} sin datos'
    cap = cv2.VideoCapture(str(out / 'video_anotado.mp4'))
    assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) == len(kps), 'el vídeo anotado no tiene todos los fotogramas'
    print(f'OK 2D: fatiga en t = {res["inicio_fatiga_s"]:.1f} s, {res["ciclos_validos"]} ciclos, vídeo anotado completo')

    try:
        import torch
        from strokelab import lift3d
    except ImportError:
        print('PyTorch no disponible: se omite la prueba del camino 3D')
        return
    ck = tmp / 'best_epoch.bin'
    torch.save({'model_pos': {'module.' + k: v for k, v in lift3d.construir_modelo().state_dict().items()}}, ck)
    analizar.main([str(vid), '--salida', str(out), '--desde-keypoints', '--motionbert', str(ck), '--sin-video'])
    res3 = json.loads((out / 'resumen.json').read_text(encoding='utf-8'))
    assert res3['angulos_3d'] is True
    assert np.load(out / 'keypoints_3d.npy').shape == (len(kps), 17, 3)
    print('OK 3D: el flujo con MotionBERT funciona (pesos aleatorios: valores no evaluados)')
    print('OK: test local superado')


if __name__ == '__main__':
    os.environ.setdefault('MPLBACKEND', 'Agg')
    main()
