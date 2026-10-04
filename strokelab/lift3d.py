"""Vertical 1 · Elevación 2D -> 3D con MotionBERT-Lite (Zhu et al., 2023), en CPU.

Adaptaciones para natación (documentadas en la memoria):
  1. Los huecos de detección se rellenan por interpolación y entran con confianza 0 (el modelo usa la confianza).
  2. Cada fotograma se centra en la pelvis y se GIRA para que el tronco quede vertical: MotionBERT se entrenó con
     personas de pie (Human3.6M) y un nadador va en horizontal. Los ángulos articulares no cambian con el giro.
  3. La escala se normaliza por el tamaño del cuerpo (mediana del tramo), no por el recorrido en la piscina.
  4. Las articulaciones sin detección 2D fiable quedan como NaN en 3D (no se inventan).

Salida: (T, 17, 3) en el ORDEN COCO-17 (como la pose 2D), en unidades normalizadas (los análisis usan ángulos
y proporciones, que no dependen de la escala).
"""
from functools import partial
from pathlib import Path

import numpy as np

CLIP = 243                     # longitud de tramo del modelo
REPO_HF = 'walterzhu/MotionBERT'
CKPT_REL = 'checkpoint/pose3d/FT_MB_lite_MB_ft_h36m_global_lite/best_epoch.bin'
URL_MANUAL = 'https://1drv.ms/f/s!AvAdh0LSjEOlgT67igq_cIoYvO2y?e=bfEc73'

# H36M-17: 0 pelvis, 1 cadD, 2 rodD, 3 tobD, 4 cadI, 5 rodI, 6 tobI, 7 columna, 8 tórax, 9 nariz, 10 cabeza,
#          11 hombroI, 12 codoI, 13 muñecaI, 14 hombroD, 15 codoD, 16 muñecaD
H36M_A_COCO = {0: 9, 1: 10, 2: 10, 3: 10, 4: 10, 5: 11, 6: 14, 7: 12, 8: 15, 9: 13, 10: 16,
               11: 4, 12: 1, 13: 5, 14: 2, 15: 6, 16: 3}
IZQ_H36M, DER_H36M = [4, 5, 6, 11, 12, 13], [1, 2, 3, 14, 15, 16]


def coco_a_h36m(x):
    """Igual que coco2h36m de MotionBERT. x: (T, 17, C) en orden COCO."""
    y = np.zeros_like(x)
    y[:, 0] = (x[:, 11] + x[:, 12]) * 0.5
    y[:, 1], y[:, 2], y[:, 3] = x[:, 12], x[:, 14], x[:, 16]
    y[:, 4], y[:, 5], y[:, 6] = x[:, 11], x[:, 13], x[:, 15]
    y[:, 8] = (x[:, 5] + x[:, 6]) * 0.5
    y[:, 7] = (y[:, 0] + y[:, 8]) * 0.5
    y[:, 9] = x[:, 0]
    y[:, 10] = (x[:, 1] + x[:, 2]) * 0.5
    y[:, 11], y[:, 12], y[:, 13] = x[:, 5], x[:, 7], x[:, 9]
    y[:, 14], y[:, 15], y[:, 16] = x[:, 6], x[:, 8], x[:, 10]
    return y


def h36m_a_coco(y):
    """(T, 17, C) H36M -> COCO-17 (los puntos de la cara se aproximan con nariz y cabeza)."""
    x = np.zeros_like(y)
    for c, h in H36M_A_COCO.items():
        x[:, c] = y[:, h]
    return x


def _rellenar(serie):
    """Interpola NaN en el tiempo (extrapola con el valor más cercano en los extremos)."""
    ok = ~np.isnan(serie)
    if not ok.any():
        return None
    t = np.arange(len(serie))
    return np.interp(t, t[ok], serie[ok])


def preparar_entrada(kps, conf):
    """kps (T,17,2) COCO px con NaN, conf (T,17) -> entrada MotionBERT (T,17,3) H36M: [x, y, conf] normalizados.

    Devuelve también la máscara de articulaciones H36M válidas (T,17).
    """
    T = len(kps)
    k = kps.astype(float).copy()
    c = np.where(np.isnan(k[..., 0]), 0.0, conf)
    for j in range(17):
        for d in range(2):
            r = _rellenar(k[:, j, d])
            k[:, j, d] = r if r is not None else np.nan
    # articulaciones nunca detectadas: en la pelvis (con confianza 0)
    pelvis = np.nanmean(k[:, [11, 12]], axis=1)
    for j in range(17):
        if np.isnan(k[:, j, 0]).all():
            k[:, j] = pelvis
            c[:, j] = 0
    h = coco_a_h36m(np.concatenate([k, c[..., None]], axis=-1))
    valido = h[..., 2] > 0
    xy = h[..., :2] - h[:, :1, :2]                        # centrar en la pelvis
    tronco = xy[:, 8]                                     # pelvis -> tórax
    ang = np.arctan2(tronco[:, 0], -tronco[:, 1])         # ángulo respecto a "arriba" (y de imagen hacia abajo)
    ang = np.nan_to_num(ang)
    cos, sen = np.cos(-ang), np.sin(-ang)
    rot = np.stack([np.stack([cos, -sen], -1), np.stack([sen, cos], -1)], -2)   # (T,2,2)
    xy = np.einsum('tij,tkj->tki', rot, xy)               # tronco vertical, cabeza arriba
    ext = np.nanmax(xy, 1) - np.nanmin(xy, 1)             # tamaño del cuerpo por fotograma
    escala = np.nanmedian(np.max(ext, 1))
    xy = xy / (escala / 2) if escala > 0 else xy          # cuerpo en [-1, 1] como en crop_scale de MotionBERT
    entrada = np.nan_to_num(np.concatenate([np.clip(xy, -1, 1), h[..., 2:3]], axis=-1)).astype(np.float32)
    return entrada, valido


def construir_modelo():
    """MotionBERT-Lite (configs/pose3d/MB_ft_h36m_global_lite.yaml)."""
    import torch.nn as nn
    from .motionbert.DSTformer import DSTformer
    return DSTformer(dim_in=3, dim_out=3, dim_feat=256, dim_rep=512, depth=5, num_heads=8, mlp_ratio=4,
                     norm_layer=partial(nn.LayerNorm, eps=1e-6), maxlen=CLIP, num_joints=17)


def localizar_checkpoint(ruta=None, carpeta_modelos='modelos'):
    """Busca best_epoch.bin; si no está, intenta descargarlo de Hugging Face."""
    candidatos = [Path(ruta)] if ruta else []
    candidatos += [Path(carpeta_modelos) / 'motionbert' / 'best_epoch.bin', Path(carpeta_modelos) / 'motionbert' / CKPT_REL]
    for c in candidatos:
        if c.exists():
            return c
    try:
        from huggingface_hub import hf_hub_download
        return Path(hf_hub_download(REPO_HF, CKPT_REL, local_dir=str(Path(carpeta_modelos) / 'motionbert')))
    except Exception as e:
        raise FileNotFoundError(
            'No encuentro el modelo de MotionBERT (best_epoch.bin).\n'
            f'  1. Descárgalo de {URL_MANUAL}\n'
            f'  2. Guárdalo como {Path(carpeta_modelos) / "motionbert" / "best_epoch.bin"}\n'
            f'  (la descarga automática falló: {type(e).__name__}: {str(e)[:150]})')


def cargar_modelo(checkpoint):
    import torch
    modelo = construir_modelo()
    ck = torch.load(str(checkpoint), map_location='cpu')
    estado = ck.get('model_pos', ck)
    estado = {k.replace('module.', '', 1): v for k, v in estado.items()}
    modelo.load_state_dict(estado, strict=True)
    modelo.eval()
    return modelo


def elevar_3d(kps, conf, modelo, voltear=True):
    """kps/conf 2D (COCO) -> (T,17,3) 3D en orden COCO. NaN donde la articulación no tenía detección 2D."""
    import torch
    entrada, valido = preparar_entrada(kps, conf)
    T = len(entrada)
    salida = np.zeros((T, 17, 3), np.float32)
    with torch.no_grad():
        for a in range(0, T, CLIP):
            x = torch.from_numpy(entrada[a:a + CLIP])[None]
            y = modelo(x)
            if voltear:      # aumento por volteo horizontal, como en infer_wild.py
                xf = x.clone()
                xf[..., 0] *= -1
                xf[..., IZQ_H36M + DER_H36M, :] = xf[..., DER_H36M + IZQ_H36M, :]
                yf = modelo(xf)
                yf[..., 0] *= -1
                yf[..., IZQ_H36M + DER_H36M, :] = yf[..., DER_H36M + IZQ_H36M, :]
                y = (y + yf) / 2
            salida[a:a + CLIP] = y[0].numpy()
    salida[~valido] = np.nan
    salida = salida - salida[:, :1]                       # relativo a la pelvis
    return h36m_a_coco(salida)
