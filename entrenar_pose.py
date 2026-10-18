"""Ajuste fino (fine-tuning) de YOLOv8n-Pose con imágenes de nadadores, por pliegues agrupados por vídeo, y evaluación
del modelo original frente al ajustado en los vídeos de prueba de cada pliegue (que nunca se usan para entrenar).

Uso:  python preparar_datos_pose.py <conjuntos...> --salida datos_pose --pliegues 4
      python entrenar_pose.py --datos datos_pose --pliegues 4 --epocas 80 [--dispositivo 0] [--salida modelos_pose]
      python entrenar_pose.py --datos datos_pose --final --epocas 60 --dispositivo 0      (modelo para usar)
Salida: modelos_pose/pliegueK/weights/best.pt, comparacion_pose.csv y comparacion_pose.json (media por pliegue).
Con --final: modelos_pose/final/weights/last.pt, entrenado con TODAS las imágenes y un número fijo de épocas. Los
pliegues miden cuánto mejora el modelo; el final es el que se usa en los vídeos (práctica habitual: evaluar con
validación cruzada y entrenar el modelo definitivo con todos los datos).
"""
import argparse
import json
from pathlib import Path

import evaluar_pose


def entrenar(yaml, nombre, salida, epocas, imgsz, dispositivo, base='yolov8n-pose.pt', paciencia=20):
    from ultralytics import YOLO
    m = YOLO(base)
    m.train(data=str(yaml), epochs=epocas, imgsz=imgsz, device=dispositivo, project=str(salida), name=nombre,
            exist_ok=True, patience=paciencia, batch=8, workers=0, fliplr=0.5, degrees=10, mosaic=1.0, plots=False, verbose=False,
            seed=0, deterministic=True)
    return Path(salida) / nombre / 'weights' / 'best.pt'


def entrenar_final(datos, salida, a):
    """Modelo definitivo: entrena con las imágenes de prueba de todos los pliegues (= todas, sin repetir). La validación
    es un subconjunto del entrenamiento, así que no se usa para parar antes ni para medir: épocas fijas y last.pt."""
    todas = sorted({l.strip() for t in sorted(datos.glob('pliegue*_test.txt')) for l in t.read_text().split('\n') if l.strip()})
    if not todas:
        raise SystemExit(f'No hay pliegues en {datos}: ejecuta antes preparar_datos_pose.py')
    (datos / 'final_train.txt').write_text('\n'.join(todas) + '\n')
    yaml = (datos / 'pliegue0.yaml').read_text(encoding='utf-8')
    yaml = yaml.replace('train: pliegue0_train.txt', 'train: final_train.txt').replace('val: pliegue0_val.txt', 'val: final_train.txt')
    (datos / 'final.yaml').write_text(yaml, encoding='utf-8')
    print(f'Modelo final: {len(todas)} imágenes, {a.epocas} épocas fijas')
    entrenar(datos / 'final.yaml', 'final', salida, a.epocas, a.imgsz, a.dispositivo, base=a.base, paciencia=a.epocas + 1)
    pesos = salida / 'final' / 'weights' / 'last.pt'
    print(f'Modelo final guardado en {pesos}')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--datos', default='datos_pose', help='carpeta creada por preparar_datos_pose.py')
    ap.add_argument('--pliegues', type=int, default=4)
    ap.add_argument('--solo', type=int, nargs='*', help='entrenar solo estos pliegues')
    ap.add_argument('--epocas', type=int, default=80)
    ap.add_argument('--imgsz', type=int, default=640)
    ap.add_argument('--dispositivo', default='cpu', help='cpu o 0 (GPU)')
    ap.add_argument('--salida', default='modelos_pose')
    ap.add_argument('--base', default='yolov8n-pose.pt', help='modelo de partida: yolov8n-pose.pt, yolov8s-pose.pt, yolov8m-pose.pt...')
    ap.add_argument('--final', action='store_true', help='entrenar el modelo definitivo con todas las imágenes')
    a = ap.parse_args(argv)
    datos, salida = Path(a.datos).resolve(), Path(a.salida).resolve()
    if a.final:
        return entrenar_final(datos, salida, a)
    filas = []
    for k in (a.solo if a.solo is not None else range(a.pliegues)):
        pesos = entrenar(datos / f'pliegue{k}.yaml', f'pliegue{k}', salida, a.epocas, a.imgsz, a.dispositivo, base=a.base)
        prueba = datos / f'pliegue{k}_test.txt'
        for etiqueta, modelo in (('original', a.base), ('ajustado', str(pesos))):
            for giro in (False, True):
                r = evaluar_pose.evaluar(datos, str(prueba), modelo, a.imgsz, 0.25, a.dispositivo, giro)
                fila = dict(pliegue=k, base=Path(a.base).stem, modelo=etiqueta, giro=giro, nadadores=r['nadadores'], deteccion=r['deteccion'],
                            OKS=r['OKS_medio'], **{f'PCK@{x}': r[f'PCK@{x}'] for x in evaluar_pose.ALFAS},
                            falsos_positivos=r['falsos_positivos'], imagenes_sin_nadador=r['imagenes_sin_nadador'],
                            por_articulacion=r['PCK@0.1_por_articulacion'])
                filas.append(fila)
                print(f"pliegue {k} · {etiqueta:8s} · giro {giro!s:5s}: detección {fila['deteccion']:.2f} · OKS {fila['OKS']:.3f} · "
                      f"PCK@0,1 {fila['PCK@0.1']:.3f}")
    import pandas as pd
    T = pd.DataFrame(filas)
    salida.mkdir(parents=True, exist_ok=True)
    T.drop(columns='por_articulacion').to_csv(salida / 'comparacion_pose.csv', index=False)
    media = T.drop(columns='por_articulacion').groupby(['modelo', 'giro']).mean(numeric_only=True).round(3)
    (salida / 'comparacion_pose.json').write_text(json.dumps(dict(
        por_pliegue=filas, media=media.reset_index().to_dict('records')), ensure_ascii=False, indent=1, default=float), encoding='utf-8')
    print('\nMedia de los pliegues (vídeos de prueba nunca vistos al entrenar):')
    print(media.drop(columns='pliegue').to_string())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
