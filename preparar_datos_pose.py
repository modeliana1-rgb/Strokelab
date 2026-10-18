"""Reparte conjuntos de imágenes de nadadores anotadas (formato YOLO-pose, 17 puntos COCO) en particiones POR VÍDEO.

Los conjuntos publicados (p. ej. Roboflow) reparten al azar fotogramas de un mismo vídeo entre entrenamiento y
prueba: fotogramas casi idénticos a ambos lados inflan el resultado (fuga de datos). Aquí cada vídeo de origen va
entero a una sola partición. Se crean k pliegues: en cada uno, un grupo de vídeos es la prueba, otro la validación y
el resto el entrenamiento. Las particiones son listas de rutas (.txt), sin copiar imágenes.

Uso:  python preparar_datos_pose.py <carpeta conjunto> [<otra carpeta> ...] --salida datos_pose --pliegues 5
      [--solo-entrenamiento <carpeta> ...]
Con --solo-entrenamiento (p. ej. imágenes sintéticas de SwimXYZ u otro conjunto), esas imágenes se añaden al
entrenamiento de TODOS los pliegues y nunca a validación ni prueba: la evaluación sigue siendo solo con imágenes reales
y comparable con la anterior.
"""
import argparse
import glob
import random
import re
from collections import defaultdict
from pathlib import Path

FLIP_COCO = [0, 2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11, 14, 13, 16, 15]
EXT = ('.jpg', '.jpeg', '.png')


def video_de(ruta):
    """Vídeo de origen de una imagen: nombre de Roboflow sin el número de fotograma ni el sufijo .rf.<hash>."""
    n = Path(ruta).name
    n = re.sub(r'\.rf\.[0-9a-f]+', '', n)
    n = re.sub(r'_(jpg|jpeg|png)$', '', Path(n).stem)
    n = re.sub(r'[-_]\d+$', '', n)                       # número de fotograma
    return re.sub(r'-\d+(_(mov|mp4))$', r'\1', n, flags=re.I).lower()   # IMG_9503-2_MOV = misma grabación que IMG_9503_MOV


def imagenes(carpetas):
    grupos = defaultdict(list)
    for c in carpetas:
        c = Path(c).resolve()
        for im in glob.glob(str(c / '**' / 'images' / '*'), recursive=True):
            if Path(im).suffix.lower() in EXT and Path(im.replace('/images/', '/labels/')).with_suffix('.txt').exists():
                grupos[f'{c.name}/{video_de(im)}'].append(im)
    return grupos


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('carpetas', nargs='+')
    ap.add_argument('--salida', default='datos_pose')
    ap.add_argument('--pliegues', type=int, default=5)
    ap.add_argument('--semilla', type=int, default=0)
    ap.add_argument('--solo-entrenamiento', nargs='*', default=[], help='conjuntos que solo se usan para entrenar')
    a = ap.parse_args(argv)
    grupos = imagenes(a.carpetas)
    extra = [im for v in imagenes(a.solo_entrenamiento).values() for im in sorted(v)] if a.solo_entrenamiento else []
    videos = sorted(grupos)
    random.Random(a.semilla).shuffle(videos)
    k = a.pliegues
    bloques = [[] for _ in range(k)]               # reparto equilibrado: cada grabación al bloque con menos imágenes
    for v in sorted(videos, key=lambda v: -len(grupos[v])):
        min(bloques, key=lambda b: sum(len(grupos[x]) for x in b)).append(v)
    out = Path(a.salida).resolve()
    out.mkdir(parents=True, exist_ok=True)
    print(f'{len(videos)} vídeos de origen, {sum(len(v) for v in grupos.values())} imágenes'
          + (f'; + {len(extra)} imágenes solo para entrenar' if extra else ''))
    for i in range(k):
        prueba, val = bloques[i], bloques[(i + 1) % k]
        entr = [v for v in videos if v not in prueba and v not in val]
        for nombre, vs in (('train', entr), ('val', val), ('test', prueba)):
            lista = [im for v in vs for im in sorted(grupos[v])] + (extra if nombre == 'train' else [])
            (out / f'pliegue{i}_{nombre}.txt').write_text('\n'.join(lista) + '\n')
        (out / f'pliegue{i}.yaml').write_text(
            f'path: {out}\ntrain: pliegue{i}_train.txt\nval: pliegue{i}_val.txt\ntest: pliegue{i}_test.txt\n'
            f'kpt_shape: [17, 3]\nflip_idx: {FLIP_COCO}\nnames:\n  0: swimmer\n', encoding='utf-8')
        n = lambda vs: sum(len(grupos[v]) for v in vs)
        print(f'  pliegue {i}: entrenamiento {n(entr) + len(extra)} imágenes ({len(entr)} vídeos) · validación {n(val)} '
              f'({len(val)}) · prueba {n(prueba)} ({len(prueba)}): {", ".join(v.split("/")[-1] for v in prueba)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
