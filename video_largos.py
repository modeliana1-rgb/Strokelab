"""Vídeo anotado por largos: tiempo de carrera, largo, frecuencia y estado de cada largo (sin nada sobre el nadador).

El estado de cada largo sale de los tiempos de paso por la pared, comparando su velocidad con la media de los
primeros largos (fase fresca):
  · RITMO ESTABLE   velocidad dentro de ±3 %
  · BAJÓN DE RITMO  más de un 3 % más lento
  · ACELERA         más de un 3 % más rápido
Debajo se explica con la frecuencia de brazos medida en ese largo (variables_por_ciclo.csv de analizar.py).

Uso:
  python video_largos.py ../videos/100_rapido.MP4 resultados/demo_rapido --salida 11 --pasos 27 43 60 75
      [--nadador "Alvise"] [--prueba "100 m libre"] [--base-largos 2] [--metros-largo 25]
Escribe <resultados>/video_largos.mp4.
"""
import argparse
import os
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

ANCHO = 1280
COLORES = {'estable': (46, 160, 90), 'bajon': (235, 104, 52), 'acelera': (42, 120, 214), 'espera': (150, 150, 150)}
TITULOS = {'estable': 'RITMO ESTABLE', 'bajon': 'BAJÓN DE RITMO', 'acelera': 'ACELERA', 'espera': ''}


def fuente(tam, negrita=False):
    import matplotlib
    nombre = 'DejaVuSans-Bold.ttf' if negrita else 'DejaVuSans.ttf'
    try:
        return ImageFont.truetype(os.path.join(matplotlib.get_data_path(), 'fonts', 'ttf', nombre), tam)
    except OSError:
        return ImageFont.load_default()


def coma(x, d=1):
    return f'{x:.{d}f}'.replace('.', ',')


def estados_largos(ciclos, limites, metros, base_largos):
    """Tabla por largo: tiempo, velocidad, frecuencia mediana, estado y explicación."""
    filas = []
    for k in range(1, len(limites)):
        a, b = limites[k - 1], limites[k]
        c = ciclos[(ciclos.t_inicio_s >= a) & (ciclos.t_inicio_s < b)]
        filas.append(dict(largo=k, desde=a, hasta=b, tiempo=b - a, v=metros / (b - a),
                          sr=float(c.SR_ciclos_min.median()) if len(c) else np.nan, n=len(c)))
    L = pd.DataFrame(filas)
    base = L[L.largo <= base_largos]
    vb, srb, tb = base.v.mean(), base.sr.mean(), base.tiempo.mean()
    est, expl = [], []
    for _, r in L.iterrows():
        sr = 'sin ciclos medidos' if np.isnan(r.sr) else f'brazos a {r.sr:.0f} ciclos/min'
        if r.largo <= base_largos:
            e, x = 'estable', f'Largo de referencia: {r.tiempo:.0f} s · {sr}'
        elif r.v < vb * 0.97:
            e = 'bajon'
            x = f'{r.tiempo - tb:+.0f} s respecto a los primeros largos · {sr} (antes {srb:.0f})'
        elif r.v > vb * 1.03:
            e = 'acelera'
            x = f'{r.tiempo:.0f} s, {r.tiempo - tb:+.0f} s respecto a los primeros largos · {sr}'
        else:
            e, x = 'estable', f'{r.tiempo:.0f} s · {sr}'
        est.append(e)
        expl.append(x)
    L['estado'], L['explicacion'] = est, expl
    return L


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('video')
    ap.add_argument('resultados', help='carpeta con variables_por_ciclo.csv')
    ap.add_argument('--salida', type=float, default=0.0, help='segundo de la salida')
    ap.add_argument('--pasos', type=float, nargs='+', required=True, help='segundo de cada toque en la pared')
    ap.add_argument('--nadador', default='')
    ap.add_argument('--prueba', default='100 m libre')
    ap.add_argument('--base-largos', type=int, default=2)
    ap.add_argument('--metros-largo', type=float, default=25.0)
    ap.add_argument('--margen', type=float, default=2.0, help='segundos de vídeo tras la llegada')
    ap.add_argument('--aproximados', action='store_true', help='los tiempos de paso son estimados, no medidos en el vídeo')
    a = ap.parse_args(argv)

    carpeta = Path(a.resultados)
    ciclos = pd.read_csv(carpeta / 'variables_por_ciclo.csv')
    limites = [a.salida] + list(a.pasos)
    L = estados_largos(ciclos, limites, a.metros_largo, a.base_largos)
    print(L[['largo', 'tiempo', 'v', 'sr', 'n', 'estado', 'explicacion']].to_string(index=False))

    cap = cv2.VideoCapture(str(a.video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    sc = min(1.0, ANCHO / W)
    OW, OH = int(W * sc) // 2 * 2, int(H * sc) // 2 * 2
    destino = carpeta / 'video_largos.mp4'
    out = cv2.VideoWriter(str(destino), cv2.VideoWriter_fourcc(*'mp4v'), fps, (OW, OH))
    fin = limites[-1] + a.margen
    f_tit, f_txt, f_big, f_peq = fuente(24, True), fuente(20), fuente(30, True), fuente(17)
    total = limites[-1] - limites[0]
    t_ini = ciclos.t_inicio_s.to_numpy()

    n = 0
    while True:
        ok, frame = cap.read()
        t = n / fps
        if not ok or t > fin:
            break
        n += 1
        if sc < 1:
            frame = cv2.resize(frame, (OW, OH), interpolation=cv2.INTER_AREA)
        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert('RGBA')
        capa = Image.new('RGBA', img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(capa)

        # Panel superior
        if t < limites[0]:
            estado, lineas = 'espera', ['Esperando la salida']
        elif t >= limites[-1]:
            estado, lineas = 'espera', [f'Llegada: {coma(total)} s']
        else:
            k = int(np.searchsorted(limites, t, side='right'))
            r = L.iloc[k - 1]
            m0 = int((k - 1) * a.metros_largo)
            previos = t_ini[(t_ini <= t) & (t_ini >= t - 3)]
            sr_txt = '--'
            if len(previos):
                sr_txt = f'{ciclos.SR_ciclos_min[t_ini == previos.max()].iloc[0]:.0f} ciclos/min'
            estado = r.estado
            lineas = [f'Tiempo de carrera  {coma(t - limites[0])} s',
                      f'Largo {k} · {m0}-{m0 + int(a.metros_largo)} m · {coma(t - r.desde)} s',
                      f'Frecuencia de brazos: {sr_txt}']
        alto = 70 + 30 * len(lineas) + (90 if estado != 'espera' else 0)
        textos = lineas + ([L.iloc[k - 1].explicacion] if estado != 'espera' else [])
        ancho = max([d.textlength(' · '.join(x for x in (a.nadador, a.prueba) if x), font=f_tit)] +
                    [d.textlength(s, font=f_txt) for s in lineas] +
                    ([d.textlength(textos[-1], font=f_peq)] if estado != 'espera' else []))
        d.rounded_rectangle((16, 16, int(48 + ancho), 16 + alto - (20 if estado != 'espera' else 0)), 12, fill=(0, 0, 0, 165))
        d.text((32, 28), ' · '.join(x for x in (a.nadador, a.prueba) if x), font=f_tit, fill='white')
        y = 66
        for s in lineas:
            d.text((32, y), s, font=f_txt, fill='white')
            y += 30
        if estado != 'espera':
            col = COLORES[estado]
            d.rounded_rectangle((32, y + 6, 32 + d.textlength(TITULOS[estado], font=f_big) + 24, y + 48), 8, fill=col + (255,))
            d.text((44, y + 9), TITULOS[estado], font=f_big, fill='white')
            d.text((32, y + 56), L.iloc[k - 1].explicacion, font=f_peq, fill='white')

        # Barra inferior: un tramo por largo, con su tiempo y su estado
        x0, x1, y1 = 30, OW - 30, OH - 24
        y0 = y1 - 44
        d.rounded_rectangle((x0 - 14, y0 - 40, x1 + 14, y1 + 14), 10, fill=(0, 0, 0, 165))
        d.text((x0, y0 - 32), 'Largos (parciales aproximados)' if a.aproximados else 'Largos (tiempo de paso por la pared)', font=f_peq, fill='white')
        X = lambda s: x0 + (x1 - x0) * (s - limites[0]) / total
        for _, r in L.iterrows():
            xa, xb = X(r.desde) + 2, X(r.hasta) - 2
            d.rectangle((xa, y0, xb, y1), fill=COLORES[r.estado] + (230,))
            etiqueta = f'L{int(r.largo)} · {r.tiempo:.0f} s · {coma(r.v, 2)} m/s'
            d.text(((xa + xb) / 2 - d.textlength(etiqueta, font=f_peq) / 2, y0 + 12), etiqueta, font=f_peq, fill='white')
        if limites[0] <= t <= limites[-1]:
            xc = X(t)
            d.line((xc, y0 - 6, xc, y1 + 6), fill='white', width=4)

        frame = cv2.cvtColor(np.array(Image.alpha_composite(img, capa).convert('RGB')), cv2.COLOR_RGB2BGR)
        out.write(frame)
    cap.release()
    out.release()
    print(f'{destino} ({n} fotogramas)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
