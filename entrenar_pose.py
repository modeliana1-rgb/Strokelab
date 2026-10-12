"""Ajuste fino (fine-tuning) de YOLOv8n-Pose con imágenes de nadadores, por pliegues agrupados por vídeo, y evaluación
del modelo original frente al ajustado en los vídeos de prueba de cada pliegue (que nunca se usan para entrenar).

Uso:  python preparar_datos_pose.py <conjuntos...> --salida datos_pose --pliegues 4
      python entrenar_pose.py --datos datos_pose --pliegues 4 --epocas 80 [--dispositivo 0] [--salida modelos_pose]
Salida: modelos_pose/pliegueK/weights/best.pt, comparacion_pose.csv y comparacion_pose.json (media por pliegue).
"""
import argparse
import json
from pathlib import Path

import evaluar_pose


def entrenar(yaml, nombre, salida, epocas, imgsz, dispositivo, base='yolov8n-pose.pt'):
    from ultralytics import YOLO
    m = YOLO(base)
    m.train(data=str(yaml), epochs=epocas, imgsz=imgsz, device=dispositivo, project=str(salida), name=nombre,
            exist_ok=True, patience=20, batch=16, fliplr=0.5, degrees=10, mosaic=1.0, plots=False, verbose=False,
            seed=0, deterministic=True)
    return Path(salida) / nombre / 'weights' / 'best.pt'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--datos', default='datos_pose', help='carpeta creada por preparar_datos_pose.py')
    ap.add_argument('--pliegues', type=int, default=4)
    ap.add_argument('--solo', type=int, nargs='*', help='entrenar solo estos pliegues')
    ap.add_argument('--epocas', type=int, default=80)
    ap.add_argument('--imgsz', type=int, default=640)
    ap.add_argument('--dispositivo', default='cpu', help='cpu o 0 (GPU)')
    ap.add_argument('--salida', default='modelos_pose')
    a = ap.parse_args(argv)
    datos, salida = Path(a.datos).resolve(), Path(a.salida).resolve()
    filas = []
    for k in (a.solo if a.solo is not None else range(a.pliegues)):
        pesos = entrenar(datos / f'pliegue{k}.yaml', f'pliegue{k}', salida, a.epocas, a.imgsz, a.dispositivo)
        prueba = datos / f'pliegue{k}_test.txt'
        for etiqueta, modelo in (('original', 'yolov8n-pose.pt'), ('ajustado', str(pesos))):
            for giro in (False, True):
                r = evaluar_pose.evaluar(datos, str(prueba), modelo, a.imgsz, 0.25, a.dispositivo, giro)
                fila = dict(pliegue=k, modelo=etiqueta, giro=giro, nadadores=r['nadadores'], deteccion=r['deteccion'],
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
