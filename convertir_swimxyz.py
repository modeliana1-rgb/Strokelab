"""Convierte SwimXYZ (nadadores SINTÉTICOS con pose exacta) al formato YOLO-pose de 17 puntos COCO.

SwimXYZ (Fiche et al., 2023, arXiv 2310.04360) guarda por secuencia una carpeta
  <vista>/<agua>/<luz>/<velocidad>/<posición>/body25/2D_cam.txt
con una fila por fotograma y columnas «Nombre.x;Nombre.y;Nombre.z» (coma decimal; x, y en píxeles de la imagen y z la
distancia a la cámara). El vídeo de la secuencia está en la misma ruta relativa dentro de la carpeta de vídeos.
Se usan los puntos BODY25 por nombre (la carpeta «COCO» trae 18 puntos con la cabecera de BODY25: más fácil equivocarse).

Se toma 1 de cada N fotogramas, se guarda la imagen y su etiqueta YOLO (caja = puntos del cuerpo + 10 % de margen; un
punto fuera de la imagen se marca como no visible). Estas imágenes van SOLO al entrenamiento
(preparar_datos_pose.py --solo-entrenamiento): la evaluación sigue siendo con nadadores reales.

Uso:  python convertir_swimxyz.py --etiquetas <carpeta de etiquetas> --videos <carpeta de vídeos> --salida swimxyz_yolo
          [--cada 15] [--max-por-secuencia 20] [--revisar 6]
  --revisar N: además guarda N imágenes con el esqueleto dibujado (revisar_*.jpg) para comprobar que los puntos caen
  sobre el nadador (si salen reflejados en vertical, repetir con --y-desde-abajo).
"""
import argparse
import glob
from pathlib import Path

import numpy as np

# COCO-17 (orden de YOLO) <- nombre BODY25 de SwimXYZ
COCO17 = ['Nose', 'LEye', 'REye', 'LEar', 'REar', 'LShoulder', 'RShoulder', 'LElbow', 'RElbow', 'LWrist', 'RWrist',
          'LHip', 'RHip', 'LKnee', 'RKnee', 'LAnkle', 'RAnkle']
HUESOS = [(5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (5, 11), (6, 12), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16)]
EXT_VIDEO = ('.mp4', '.avi', '.mov', '.mkv', '.webm')


def leer_2d(txt):
    """(fotogramas, 17, 2) en el orden COCO-17, a partir del 2D_cam.txt de BODY25."""
    filas = Path(txt).read_text(encoding='utf-8', errors='ignore').splitlines()
    cab = [c for c in filas[0].strip().strip(';').split(';')]
    datos = []
    for f in filas[1:]:
        v = [x for x in f.strip().strip(';').split(';') if x != '']
        if len(v) == len(cab):
            datos.append([float(x.replace(',', '.')) for x in v])
    A = np.array(datos)
    idx = {c: i for i, c in enumerate(cab)}
    return np.stack([A[:, [idx[f'{n}.x'], idx[f'{n}.y']]] for n in COCO17], axis=1)


def video_de(seq_dir, etiquetas, videos):
    """Vídeo con la misma ruta relativa que la carpeta de la secuencia (o dentro de ella)."""
    rel = seq_dir.relative_to(etiquetas)
    base = Path(videos) / rel
    for cand in [base.with_suffix(e) for e in EXT_VIDEO] + sorted(p for p in base.glob('*') if p.suffix.lower() in EXT_VIDEO):
        if cand.exists():
            return cand
    # por si la carpeta de vídeos empieza un nivel más abajo o más arriba
    for cand in Path(videos).rglob('*'):
        if cand.suffix.lower() in EXT_VIDEO and cand.with_suffix('').as_posix().endswith(rel.as_posix()):
            return cand
    return None


def main(argv=None):
    import cv2
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--etiquetas', required=True)
    ap.add_argument('--videos', required=True)
    ap.add_argument('--salida', default='swimxyz_yolo')
    ap.add_argument('--cada', type=int, default=15, help='1 de cada N fotogramas (los seguidos son casi iguales)')
    ap.add_argument('--max-por-secuencia', type=int, default=20)
    ap.add_argument('--y-desde-abajo', action='store_true', help='si la y de SwimXYZ cuenta desde abajo de la imagen')
    ap.add_argument('--revisar', type=int, default=0, help='guardar N imágenes con el esqueleto dibujado')
    a = ap.parse_args(argv)
    etiquetas = Path(a.etiquetas).resolve()
    out = Path(a.salida).resolve()
    (out / 'train' / 'images').mkdir(parents=True, exist_ok=True)
    (out / 'train' / 'labels').mkdir(parents=True, exist_ok=True)
    secuencias = sorted({Path(t).parent.parent for t in glob.glob(str(etiquetas / '**' / 'body25' / '2D_cam.txt'), recursive=True)})
    print(f'{len(secuencias)} secuencias con etiquetas')
    n_img = n_sin_video = revisadas = 0
    for s in secuencias:
        vid = video_de(s, etiquetas, a.videos)
        if vid is None:
            n_sin_video += 1
            continue
        kp = leer_2d(s / 'body25' / '2D_cam.txt')
        cap = cv2.VideoCapture(str(vid))
        nfr = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if nfr and abs(nfr - len(kp)) > 2:
            print(f'  AVISO {s.relative_to(etiquetas)}: {nfr} fotogramas de vídeo y {len(kp)} de etiquetas')
        nombre = '_'.join(s.relative_to(etiquetas).parts).replace(',', 'p').replace(' ', '')
        guardadas = 0
        for i in range(0, min(len(kp), nfr or len(kp)), a.cada):
            if guardadas >= a.max_por_secuencia:
                break
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ok, img = cap.read()
            if not ok:
                break
            h, w = img.shape[:2]
            p = kp[i].copy()
            if a.y_desde_abajo:
                p[:, 1] = h - p[:, 1]
            dentro = (p[:, 0] >= 0) & (p[:, 0] < w) & (p[:, 1] >= 0) & (p[:, 1] < h)
            if dentro.sum() < 8:                                  # nadador casi fuera de la imagen
                continue
            q = p[dentro]
            x0, y0 = q.min(0)
            x1, y1 = q.max(0)
            mx, my = 0.1 * (x1 - x0) + 5, 0.1 * (y1 - y0) + 5
            x0, y0, x1, y1 = max(0, x0 - mx), max(0, y0 - my), min(w, x1 + mx), min(h, y1 + my)
            caja = [(x0 + x1) / 2 / w, (y0 + y1) / 2 / h, (x1 - x0) / w, (y1 - y0) / h]
            pts = []
            for (x, y), d in zip(p, dentro):
                pts += [x / w, y / h, 2] if d else [0, 0, 0]
            stem = f'{nombre}_{i:05d}'
            cv2.imwrite(str(out / 'train' / 'images' / f'{stem}.jpg'), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
            (out / 'train' / 'labels' / f'{stem}.txt').write_text(
                '0 ' + ' '.join(f'{v:.6f}' if isinstance(v, float) else str(v) for v in caja + pts) + '\n')
            guardadas += 1
            n_img += 1
            if revisadas < a.revisar:
                dib = img.copy()
                for i0, i1 in HUESOS:
                    if dentro[i0] and dentro[i1]:
                        cv2.line(dib, tuple(map(int, p[i0])), tuple(map(int, p[i1])), (0, 255, 0), 2)
                cv2.rectangle(dib, (int(x0), int(y0)), (int(x1), int(y1)), (0, 0, 255), 2)
                cv2.imwrite(str(out / f'revisar_{revisadas}.jpg'), dib)
                revisadas += 1
        cap.release()
    print(f'{n_img} imágenes guardadas en {out / "train"}; {n_sin_video} secuencias sin vídeo')
    if a.revisar:
        print(f'Revisa {out}/revisar_*.jpg: el esqueleto verde debe caer sobre el nadador '
              '(si sale reflejado arriba/abajo, repite con --y-desde-abajo).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
