"""Precisión del modelo de pose sobre imágenes de nadadores anotadas (formato YOLO-pose, 17 puntos COCO).

Métricas (memoria, Capítulo 2):
  - PCK@a: proporción de articulaciones anotadas cuya predicción cae a menos de a·max(ancho, alto) de la caja del
    nadador (a = 0,05, 0,1 y 0,2), por articulación y en total.
  - OKS: similitud de puntos clave de COCO (sigmas oficiales, escala = área de la caja), media por nadador.
  - mAP de pose (OKS) con el evaluador de Ultralytics (mAP50 y mAP50-95), el estándar de la literatura.
  - Detección: proporción de nadadores anotados para los que el modelo da alguna pose (OKS > 0).
Cada nadador anotado se empareja con la predicción de mayor OKS.

Uso:  python evaluar_pose.py --datos <carpeta del conjunto con data.yaml> --split test [--modelo yolov8n-pose.pt]
      [--imgsz 640] [--salida resultados_pose]
"""
import argparse
import glob
import json
from pathlib import Path

import numpy as np

NOMBRES = ['nariz', 'ojo I', 'ojo D', 'oreja I', 'oreja D', 'hombro I', 'hombro D', 'codo I', 'codo D', 'muñeca I',
           'muñeca D', 'cadera I', 'cadera D', 'rodilla I', 'rodilla D', 'tobillo I', 'tobillo D']
SIGMAS = np.array([.26, .25, .25, .35, .35, .79, .79, .72, .72, .62, .62, 1.07, 1.07, .87, .87, .89, .89]) / 10
FLIP_COCO = [0, 2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11, 14, 13, 16, 15]
ALFAS = (0.05, 0.1, 0.2)


def leer_etiquetas(txt, w, h):
    """Nadadores anotados: lista de (caja xywh en px, puntos (17,3) en px con visibilidad)."""
    out = []
    for linea in Path(txt).read_text().split('\n'):
        p = linea.split()
        if len(p) < 5 + 17 * 2:
            continue
        v = np.array(p, float)
        caja = v[1:5] * [w, h, w, h]
        k = v[5:].reshape(17, -1)
        k = np.c_[k[:, 0] * w, k[:, 1] * h, k[:, 2] if k.shape[1] > 2 else np.ones(17) * 2]
        out.append((caja, k))
    return out


def oks(pred, gt, area):
    vis = gt[:, 2] > 0
    if not vis.any():
        return np.nan
    d2 = ((pred[:, :2] - gt[:, :2]) ** 2).sum(1)
    e = d2 / (2 * (SIGMAS * 2) ** 2 * (area + np.spacing(1)))
    return float(np.mean(np.exp(-e[vis])))


def _predecir(m, im, imgsz, conf, dispositivo, girar):
    """Poses predichas (lista de (17,3) en px de la imagen original). Con girar, además de la imagen original se
    prueban giros de ±90° (como hace StrokeLab con nadadores horizontales) y se conserva el giro cuya detección
    tiene más confianza; las coordenadas se devuelven a la imagen original. No usa la anotación."""
    import cv2
    from strokelab.pose import girar as girar_img, desgirar
    img = cv2.imread(im)
    h, w = img.shape[:2]
    mejor, mejor_c = [], -1.0
    for rot in ((0, 90, -90) if girar else (0,)):
        r = m(girar_img(img, rot), verbose=False, imgsz=imgsz, conf=conf, device=dispositivo)[0]
        if r.keypoints is None or not len(r.boxes):
            continue
        c = float(r.boxes.conf.max())
        if c > mejor_c:
            xy = r.keypoints.xy.cpu().numpy()
            mejor = [np.c_[desgirar(xy[i], rot, w, h), np.ones(17)] for i in range(len(xy))]
            mejor_c = c
    return mejor, (h, w)


def evaluar(datos, split, modelo='yolov8n-pose.pt', imgsz=640, conf=0.25, dispositivo='cpu', girar=False):
    from ultralytics import YOLO
    m = YOLO(modelo)
    if str(split).endswith('.txt'):              # lista de imágenes (pliegues de preparar_datos_pose.py)
        imgs = [l.strip() for l in Path(split).read_text().split('\n') if l.strip()]
    else:
        imgs = sorted(glob.glob(str(Path(datos) / split / 'images' / '*')))
    filas = []                                   # una por nadador anotado
    falsos = 0                                   # imágenes sin nadador en las que el modelo ve alguno
    vacias = 0
    for im in imgs:
        txt = Path(im.replace('/images/', '/labels/')).with_suffix('.txt')
        preds, (h, w) = _predecir(m, im, imgsz, conf, dispositivo, girar)
        gts = leer_etiquetas(txt, w, h) if txt.exists() else []
        if not gts:
            vacias += 1
            falsos += bool(preds)
            continue
        for caja, gt in gts:
            area = caja[2] * caja[3]
            mejores = [(oks(p, gt, area), p) for p in preds]
            o, p = max(mejores, key=lambda t: t[0]) if mejores else (0.0, None)
            escala = max(caja[2], caja[3])
            dist = np.full(17, np.nan)
            if p is not None:
                dist = np.linalg.norm(p[:, :2] - gt[:, :2], axis=1) / escala
            dist[gt[:, 2] <= 0] = np.nan              # solo articulaciones anotadas
            filas.append(dict(imagen=Path(im).name, oks=o, detectado=p is not None and o > 0, dist=dist,
                              anotadas=(gt[:, 2] > 0)))
    D = np.array([f['dist'] for f in filas])
    A = np.array([f['anotadas'] for f in filas])
    res = dict(modelo=str(modelo), split=split, imgsz=imgsz, conf=conf, giro=girar, imagenes=len(imgs), nadadores=len(filas),
               imagenes_sin_nadador=vacias, falsos_positivos=falsos,
               deteccion=float(np.mean([f['detectado'] for f in filas])) if filas else None,
               OKS_medio=float(np.nanmean([f['oks'] for f in filas])) if filas else None)
    for a in ALFAS:
        acierto = np.where(A, np.nan_to_num(D, nan=np.inf) < a, np.nan)        # sin predicción = fallo
        res[f'PCK@{a}'] = float(np.nanmean(acierto))
        res[f'PCK@{a}_por_articulacion'] = {NOMBRES[j]: round(float(np.nanmean(acierto[:, j])), 3) for j in range(17)}
    return res


def map_ultralytics(datos, split, modelo='yolov8n-pose.pt', imgsz=640, dispositivo='cpu'):
    """mAP de pose (OKS) con el evaluador oficial de Ultralytics."""
    from ultralytics import YOLO
    yaml = Path(datos) / 'strokelab_data.yaml'
    yaml.write_text(f'path: {Path(datos).resolve()}\ntrain: train/images\nval: {split}/images\ntest: test/images\n'
                    f'kpt_shape: [17, 3]\nflip_idx: {FLIP_COCO}\nnames:\n  0: swimmer\n', encoding='utf-8')
    r = YOLO(modelo).val(data=str(yaml), split='val', imgsz=imgsz, device=dispositivo, verbose=False, plots=False)
    return dict(pose_mAP50=float(r.pose.map50), pose_mAP50_95=float(r.pose.map),
                caja_mAP50=float(r.box.map50), caja_mAP50_95=float(r.box.map))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--datos', required=True)
    ap.add_argument('--split', default='test')
    ap.add_argument('--modelo', default='yolov8n-pose.pt')
    ap.add_argument('--imgsz', type=int, default=640)
    ap.add_argument('--dispositivo', default='cpu')
    ap.add_argument('--conf', type=float, default=0.25, help='confianza mínima de la detección')
    ap.add_argument('--girar', action='store_true', help='probar también la imagen girada ±90° (como StrokeLab)')
    ap.add_argument('--sin-map', action='store_true', help='no calcular el mAP de Ultralytics')
    ap.add_argument('--salida', default='resultados_pose')
    a = ap.parse_args(argv)
    res = evaluar(a.datos, a.split, a.modelo, a.imgsz, a.conf, a.dispositivo, a.girar)
    if not a.sin_map:
        try:
            res.update(map_ultralytics(a.datos, a.split, a.modelo, a.imgsz, a.dispositivo))
        except Exception as e:                   # el mAP oficial es un complemento
            res['mAP_error'] = f'{type(e).__name__}: {e}'
    out = Path(a.salida)
    out.mkdir(parents=True, exist_ok=True)
    nombre = f'pose_{Path(a.modelo).parent.parent.name if Path(a.modelo).parent.name == "weights" else Path(a.modelo).stem}_{Path(a.split).stem}_{a.imgsz}_c{a.conf}{"_giro" if a.girar else ""}.json'
    (out / nombre).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in res.items() if 'por_articulacion' not in k}, ensure_ascii=False, indent=2))
    print('PCK@0,1 por articulación:', res['PCK@0.1_por_articulacion'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
