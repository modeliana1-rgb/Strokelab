"""StrokeLab · análisis EN TIEMPO REAL: el vídeo se reproduce mientras se analiza y el panel muestra, ciclo a ciclo,
el estado de fatiga (CALIBRANDO -> FRESCO -> FATIGA), sus causas (SHAP), el estilo y la vista.

Solo usa lo ya nadado (como en una sesión en directo): la fase base son los primeros --base-ciclos ciclos
(fatiga.FatigaEnVivo). El análisis completo de un vídeo terminado sigue siendo analizar.py / lote.py.

Uso (PowerShell, desde la carpeta del proyecto):
  python en_vivo.py "C:\\...\\GX011614.MP4" --nadador P1                     # pose en directo (YOLO; GPU si hay)
  python en_vivo.py 0 --nadador P1                                          # cámara web / capturadora
  python en_vivo.py "C:\\...\\GX011614.MP4" --resultados ..\\resultados\\GX011614   # sin YOLO: reutiliza la pose ya
                                                                            # extraída por lote.py (siempre fluido)
Teclas: q o Esc = salir, espacio = pausa. --guardar salida.mp4 graba lo que se ve; --sin-ventana para el clúster.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')

import cv2
import numpy as np
import pandas as pd

from strokelab import estilo as estilos, fatiga, medidas, pose, vista as vistas
from strokelab.pose import SKELETON

VENTANA_S = 30.0     # segundos de pose que se reanalizan en cada paso
PASO_S = 1.0         # cada cuánto se buscan ciclos nuevos
VERDE, ROJO, AMARILLO, BLANCO, GRIS = (60, 200, 60), (40, 40, 230), (0, 200, 230), (255, 255, 255), (150, 150, 150)
FUENTE = cv2.FONT_HERSHEY_SIMPLEX


class AnalizadorEnVivo:
    """Acumula la pose fotograma a fotograma y extrae ciclos nuevos con las mismas funciones que el análisis completo."""

    def __init__(self, fps, ancho, estilo='auto', vista='auto', n_base=10):
        self.fps, self.ancho = fps, ancho
        self.estilo_pedido, self.vista_pedida = estilo, vista
        self.estilo = estilo if estilo != 'auto' else None
        self.estilo_info = None
        self.vista = vista if vista != 'auto' else None
        self.kps, self.conf = [], []
        self.fat = fatiga.FatigaEnVivo(n_base=n_base)
        self.ciclos = []                 # filas de los ciclos ya registrados (tiempo absoluto)
        self.ultimo_fin = -1.0
        self.ultimo_paso = 0
        self.ultimo_estado = dict(estado='CALIBRANDO', ciclo=0, base=n_base, causas=[])

    def agregar(self, xy, cf):
        self.kps.append(xy)
        self.conf.append(cf)
        n = len(self.kps)
        if n - self.ultimo_paso >= PASO_S * self.fps and n >= 6 * self.fps:
            self.ultimo_paso = n
            self._paso()

    def _paso(self):
        fps = self.fps
        n = len(self.kps)
        w0 = max(0, n - int(VENTANA_S * fps))
        k2d, _ = medidas.limpiar(np.array(self.kps[w0:]), np.array(self.conf[w0:]), fps)
        if self.vista_pedida == 'auto':             # vista de los últimos 30 s por la orientación del tronco
            v = vistas.tronco_vertical(k2d)
            if np.sum(~np.isnan(v)) >= 2 * fps:
                self.vista = 'frontal' if np.nanmean(v) >= vistas.UMBRAL_FRACCION else 'lateral'
        if self.vista is None:
            return
        if self.estilo_pedido == 'auto' and (self.estilo_info is None or self.estilo_info['seguridad'] == 'baja'):
            info = estilos.estimar_por_reglas(k2d, fps, [(0, len(k2d), self.vista)])
            if info['estilo_para_ciclos']:
                self.estilo_info, self.estilo = info, info['estilo_para_ciclos']
        if self.estilo is None:
            return
        fr = medidas.medidas_por_fotograma(k2d, fps, vista=self.vista)
        _, _, ciclos_ab, _ = medidas.detectar_ciclos(fr, fps, self.estilo, self.vista)
        margen = int(0.1 * fps)
        nuevos = [(a, b) for a, b in ciclos_ab if b < len(k2d) - margen and (w0 + a) / fps >= self.ultimo_fin - 0.15]
        if not nuevos:
            return
        tabla = medidas.variables_por_ciclo(fr, fps, nuevos, None, self.ancho, self.estilo, self.vista)
        for _, c in tabla.iterrows():
            t0 = c.t_inicio_s + w0 / fps
            if t0 < self.ultimo_fin - 0.15:
                continue
            fila = c.to_dict()
            fila.update(t_inicio_s=round(t0, 2), vista=self.vista, estilo=self.estilo, ciclo=len(self.ciclos) + 1)
            self.ultimo_estado = self.fat.agregar(fila)
            fila.update(estado=self.ultimo_estado['estado'], anomalia=self.ultimo_estado.get('anomalia'))
            self.ciclos.append(fila)
            self.ultimo_fin = t0 + c.duracion_s

    def resumen(self, nadador):
        e = self.ultimo_estado
        ini = self.fat.inicio
        return dict(nadador=nadador, ciclos=len(self.ciclos), estilo=self.estilo, estilo_pedido=self.estilo_pedido,
                    estilo_estimado=(self.estilo_info or {}).get('estilo'), vista=self.vista, base_ciclos=self.fat.n_base,
                    estado_final=e['estado'], umbral=getattr(self.fat, 'umbral', None),
                    inicio_fatiga_ciclo=None if ini is None else ini + 1,
                    inicio_fatiga_s=None if ini is None else self.ciclos[ini]['t_inicio_s'])


def _caja(f, x0, y0, x1, y1, alfa=0.6):
    f[y0:y1, x0:x1] = (f[y0:y1, x0:x1] * (1 - alfa)).astype(f.dtype)


def dibujar(f, xy, an, t, nadador, fps_proc):
    """Esqueleto del último fotograma y panel con el estado del análisis en directo."""
    e = an.ultimo_estado
    col = {'FATIGA': ROJO, 'FRESCO': VERDE}.get(e['estado'], AMARILLO)
    if xy is not None and not np.isnan(xy).all():
        for a, b in SKELETON:
            if not np.isnan(xy[[a, b]]).any():
                cv2.line(f, tuple(xy[a].astype(int)), tuple(xy[b].astype(int)), col, 3, cv2.LINE_AA)
    est = an.estilo or 'estimando...'
    if an.estilo_pedido == 'auto' and an.estilo_info:
        est = f'{an.estilo_info["estilo"] or an.estilo_info["familia"]} (auto, {an.estilo_info["seguridad"]})'
    ult = an.ciclos[-1] if an.ciclos else None
    lineas = [(f'{nadador}   t = {t:5.1f} s   ({fps_proc:4.1f} fps)', BLANCO, 0.55, 1),
              (f'Estilo: {est}   Vista: {an.vista or "estimando..."}', BLANCO, 0.55, 1),
              (f'Ciclo {len(an.ciclos)}' + (f'   {ult["SR_ciclos_min"]:4.1f} ciclos/min' if ult else ''), BLANCO, 0.6, 1)]
    if e['estado'] == 'CALIBRANDO':
        lineas.append((f'CALIBRANDO {min(len(an.ciclos), an.fat.n_base)}/{an.fat.n_base} ciclos', AMARILLO, 0.8, 2))
    else:
        lineas.append((e['estado'], col, 1.1, 3))
        if an.fat.inicio is not None:
            lineas.append((f'desde el ciclo {an.fat.inicio + 1} (t = {an.ciclos[an.fat.inicio]["t_inicio_s"]:.1f} s)', ROJO, 0.55, 1))
        for c in e.get('causas', [])[:2]:
            lineas.append((f'{c["nombre"].split(" (")[0]}: {c["base"]:.1f} -> {c["ahora"]:.1f}', BLANCO, 0.5, 1))
    alto = 14 + sum(int(34 * s) + 6 for _, _, s, _ in lineas)
    _caja(f, 10, 10, 470, 10 + alto)
    y = 18
    for s, c_, esc, g in lineas:
        y += int(34 * esc)
        cv2.putText(f, s, (22, y), FUENTE, esc, c_, g, cv2.LINE_AA)
        y += 6
    if an.fat.modelo is not None and an.fat.anom:          # barra: anomalía de los últimos 40 ciclos y umbral
        h, w = f.shape[:2]
        x0, x1, y1, alto_b = 20, min(w - 20, 620), h - 20, 60
        _caja(f, x0 - 8, y1 - alto_b - 26, x1 + 8, y1 + 8)
        cv2.putText(f, 'Fatiga por ciclo (ultimos 40)', (x0, y1 - alto_b - 8), FUENTE, 0.5, BLANCO, 1, cv2.LINE_AA)
        a = np.array(an.fat.anom[-40:])
        lo, hi = min(a.min(), an.fat.umbral) - 1e-3, max(a.max(), an.fat.umbral) + 1e-3
        Y = lambda v: int(y1 - (v - lo) / (hi - lo) * alto_b)
        ancho = (x1 - x0) / 40
        for i, v in enumerate(a):
            c_ = ROJO if v > an.fat.umbral else VERDE
            cv2.rectangle(f, (int(x0 + i * ancho), Y(v)), (int(x0 + (i + 1) * ancho) - 2, y1), c_, -1)
        cv2.line(f, (x0, Y(an.fat.umbral)), (x1, Y(an.fat.umbral)), BLANCO, 1)
    return f


def main(argv=None):
    ap = argparse.ArgumentParser(description='Análisis en tiempo real con el estado de fatiga en pantalla.')
    ap.add_argument('fuente', help='vídeo o número de cámara (0, 1...)')
    ap.add_argument('--nadador', default='Nadador')
    ap.add_argument('--estilo', default='auto', choices=list(medidas.ESTILOS) + ['auto'])
    ap.add_argument('--vista', default='auto', choices=['auto', 'lateral', 'frontal'])
    ap.add_argument('--base-ciclos', type=int, default=10, help='ciclos de la fase base (estado fresco del nadador)')
    ap.add_argument('--resultados', help='carpeta de resultados del vídeo (keypoints_raw.npz): sin YOLO')
    ap.add_argument('--modelo', default='yolov8n-pose')
    ap.add_argument('--cada', type=int, default=2, help='pose en 1 de cada N fotogramas')
    ap.add_argument('--imgsz', type=int, default=640)
    ap.add_argument('--girar', default='0', choices=['0', '90', '-90', 'auto'])
    ap.add_argument('--dispositivo', default='auto')
    ap.add_argument('--guardar', help='grabar lo que se muestra (mp4)')
    ap.add_argument('--salida', help='carpeta para ciclos_en_vivo.csv y resumen_en_vivo.json')
    ap.add_argument('--sin-ventana', action='store_true', help='no abrir ventana (clúster o pruebas)')
    ap.add_argument('--tiempo-real', action='store_true', help='con --resultados, reproducir a la velocidad del vídeo')
    a = ap.parse_args(argv)

    camara = a.fuente.isdigit()
    cap = cv2.VideoCapture(int(a.fuente) if camara else a.fuente) if (camara or Path(a.fuente).exists()) else None
    kps_previos = None
    if a.resultados:
        with np.load(Path(a.resultados) / 'keypoints_raw.npz') as _npz:          # Windows: el archivo se cierra al terminar de leerlo
            d = dict(_npz)
        kps_previos, conf_previos = d['kps'], d['conf']
        fps, W, H = float(d['fps']), int(d['w']), int(d['h'])
    elif cap is None or not cap.isOpened():
        print(f'No se puede abrir: {a.fuente}')
        return 1
    if cap is not None and cap.isOpened():
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    est = None
    if kps_previos is None:
        pose.YOLO_IMGSZ = a.imgsz
        pose.DISPOSITIVO = pose.elegir_dispositivo(a.dispositivo)
        rot = pose.elegir_rotacion(a.fuente, a.modelo) if a.girar == 'auto' and not camara else int(a.girar if a.girar != 'auto' else 0)
        f_red = min(1.0, pose.MAX_LADO / max(W, H))
        est = pose.EstimadorGirado(a.modelo, int(round(W * f_red)), int(round(H * f_red)), rot)
        print(f'Pose en directo con {a.modelo} en {pose.DISPOSITIVO} (1 de cada {a.cada} fotogramas)')
    an = AnalizadorEnVivo(fps, W, a.estilo, a.vista, a.base_ciclos)
    sc = min(1.0, 1280 / W)
    escritor = None
    if a.guardar:
        escritor = cv2.VideoWriter(a.guardar, cv2.VideoWriter_fourcc(*'mp4v'), fps, (int(W * sc), int(H * sc)))
    N = len(kps_previos) if kps_previos is not None else int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) if not camara else 10 ** 9
    t_ini, pausa, i = time.time(), False, 0
    xy, cf = np.full((17, 2), np.nan), np.zeros(17)
    while i < N:
        f = None
        if cap is not None and cap.isOpened():
            ok, f = cap.read()
            if not ok:
                break
        if kps_previos is not None:
            xy, cf = kps_previos[i], conf_previos[i]
        elif i % a.cada == 0:
            fr_, red = pose.reducir(f)
            xy, cf = est(fr_)
            xy = xy / red
        else:
            xy, cf = np.full((17, 2), np.nan), np.zeros(17)
        an.agregar(xy, cf)
        if not a.sin_ventana or escritor is not None:
            if f is None:
                f = np.zeros((H, W, 3), np.uint8)
            if sc < 1:
                f = cv2.resize(f, (int(W * sc), int(H * sc)), interpolation=cv2.INTER_AREA)
            fps_proc = (i + 1) / max(time.time() - t_ini, 1e-6)
            f = dibujar(f, xy * sc if xy is not None else None, an, i / fps, a.nadador, fps_proc)
            if escritor is not None:
                escritor.write(f)
            if not a.sin_ventana:
                cv2.imshow('StrokeLab en vivo', f)
                espera = 1
                if a.tiempo_real or kps_previos is None and not camara:   # no ir más rápido que el vídeo
                    espera = max(1, int(1000 * ((i + 1) / fps - (time.time() - t_ini))))
                tecla = cv2.waitKey(espera) & 0xFF
                if tecla in (ord('q'), 27):
                    break
                if tecla == ord(' '):
                    pausa = not pausa
                while pausa:
                    tecla = cv2.waitKey(50) & 0xFF
                    if tecla in (ord(' '), ord('q'), 27):
                        pausa = False
        i += 1
    if cap is not None:
        cap.release()
    if escritor is not None:
        escritor.release()
    if not a.sin_ventana:
        cv2.destroyAllWindows()
    res = an.resumen(a.nadador)
    print(json.dumps(res, ensure_ascii=False, indent=2, default=float))
    if a.salida:
        out = Path(a.salida)
        out.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(an.ciclos).to_csv(out / 'ciclos_en_vivo.csv', index=False)
        (out / 'resumen_en_vivo.json').write_text(json.dumps(res, ensure_ascii=False, indent=2, default=float), encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
