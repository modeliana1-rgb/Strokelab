"""Genera StrokeLab_v3_pipeline.ipynb (Colab)."""
import os
import nbformat as nbf

cells = []  # (tipo, fuente, colab_only)


def md(s):
    cells.append(("md", s.strip(), False))


def code(s, colab_only=False):
    cells.append(("code", s.strip(), colab_only))


md("""
# StrokeLab v3: pipeline limpio (1 nadador, crol)

**Vertical 1 (Visión):** vídeo → estimación de pose 2D (comparativa de modelos) → keypoints COCO-17 limpios.
**Vertical 2 (Tabulares):** keypoints → features por ciclo de brazada → eficiencia → fatiga (Isolation Forest + SHAP).

**Cómo usarlo:**
1. `Entorno de ejecución → Cambiar tipo → GPU (T4)`.
2. Edita la celda **CONFIGURACIÓN** (ruta del vídeo y calibración).
3. `Entorno de ejecución → Ejecutar todas`.

Todo se guarda en `OUT_DIR` (CSV, JSON, figuras PNG y vídeo anotado), listo para la memoria.
""")

md("## 0. Instalación")
code("""
!pip -q install ultralytics ruptures shap xgboost tensorflow_hub
""", colab_only=True)

md("## 1. CONFIGURACIÓN (edita solo esta celda)")
code("""
from google.colab import drive
drive.mount('/content/drive')

VIDEO_PATH = '/content/drive/MyDrive/Videos_TFM/Nadador A/GX011615.MP4'   # <- tu vídeo (crol)
OUT_DIR    = '/content/drive/MyDrive/Videos_TFM/resultados_v3/Nadador A'    # <- carpeta de salida
NADADOR    = 'Nadador A'

# Calibración (solo si la CÁMARA ESTÁ FIJA): metros horizontales que abarca el encuadre.
# Ejemplo: si de borde a borde del vídeo se ven 2.5 m -> 2.5.  Si la cámara se mueve -> None.
METROS_ANCHO_ENCUADRE = None

# Modelo de pose para la extracción. Decisión del TFM: MoveNet (vídeo fluido, sin tirones).
# YOLO se mide igualmente en la comparativa como alternativa.
POSE_BACKEND    = 'movenet'      # 'movenet' o 'yolo'
MOVENET_VARIANT = 'lightning'    # 'lightning' (rápido, 192 px) o 'thunder' (más preciso, 256 px)

import os, glob
if not os.path.exists(VIDEO_PATH):
    print('No encuentro el vídeo:', VIDEO_PATH)
    print('Vídeos disponibles en la carpeta:')
    for v in sorted(glob.glob(os.path.join(os.path.dirname(VIDEO_PATH), '*'))): print('  ', v)
    raise FileNotFoundError('Copia una de las rutas de arriba en VIDEO_PATH')
print('Vídeo OK:', VIDEO_PATH, f'({os.path.getsize(VIDEO_PATH)/1e6:.0f} MB)')
""", colab_only=True)

code("""
import os, json, time, warnings, cv2
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, savgol_filter
warnings.filterwarnings('ignore')

CONF_KP = 0.30            # confianza mínima por keypoint
N_FRAMES_BENCH = 150      # frames usados en la comparativa de modelos
MAX_ANCHO = 1280          # los vídeos 4K se reducen a este ancho donde no hace falta resolución completa
BASELINE_FRAC = 0.30      # % inicial de ciclos considerado "fresco"
os.makedirs(OUT_DIR, exist_ok=True)
FIG = lambda name: os.path.join(OUT_DIR, name)

# Índices COCO-17
NOSE, LSH, RSH, LEL, REL, LWR, RWR, LHIP, RHIP, LKN, RKN, LAN, RAN = 0, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16
SKELETON = [(5,7),(7,9),(6,8),(8,10),(5,6),(5,11),(6,12),(11,12),(11,13),(13,15),(12,14),(14,16),(0,5),(0,6)]
""")

md("""
## 2. Vertical 1 · MoveNet con recorte que sigue al nadador
MoveNet trabaja con una imagen cuadrada pequeña (192 px en Lightning). En un vídeo 4K el nadador
quedaría diminuto, así que se aplica el **recorte de seguimiento** de MoveNet: cada fotograma se recorta
en un cuadrado alrededor de la posición anterior del nadador.

Como el recorte ya es cuadrado, no hay relleno que deshacer, y las coordenadas vuelven al vídeo original con
`x = x0 + x_norm · lado`, `y = y0 + y_norm · lado`. Esto evita el error de escalado de versiones anteriores.
""")
code("""
def recorte_cuadrado(frame, cx, cy, lado):
    \"\"\"Cuadrado de 'lado' px centrado en (cx, cy); lo que cae fuera del vídeo queda en negro.\"\"\"
    alto, ancho = frame.shape[:2]; lado = int(round(lado))
    x0, y0 = int(round(cx - lado / 2)), int(round(cy - lado / 2))
    lienzo = np.zeros((lado, lado, 3), frame.dtype)
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(ancho, x0 + lado), min(alto, y0 + lado)
    if xb > xa and yb > ya:
        lienzo[ya - y0:yb - y0, xa - x0:xb - x0] = frame[ya:yb, xa:xb]
    return lienzo, x0, y0, lado

class SeguidorMoveNet:
    \"\"\"MoveNet + recorte de seguimiento. infer(rgb tam x tam) -> (17, 3) con [y, x, score] normalizados.\"\"\"
    def __init__(self, infer, tam, ancho, alto, umbral=0.2):
        self.infer, self.tam, self.ancho, self.alto, self.umbral = infer, tam, ancho, alto, umbral
        self.region = None
    def __call__(self, frame):
        lado_max = max(self.ancho, self.alto)
        cx, cy, lado = self.region or (self.ancho / 2, self.alto / 2, lado_max)
        img, x0, y0, lado = recorte_cuadrado(frame, cx, cy, lado)
        rgb = cv2.cvtColor(cv2.resize(img, (self.tam, self.tam), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
        out = self.infer(rgb)
        xy = np.c_[x0 + out[:, 1] * lado, y0 + out[:, 0] * lado]; sc = out[:, 2]
        ok = sc > self.umbral
        if ok.sum() >= 5:                                   # siguiente recorte: caja del cuerpo x 1.6
            (xa, ya), (xb, yb) = xy[ok].min(0), xy[ok].max(0)
            self.region = ((xa + xb) / 2, (ya + yb) / 2, float(np.clip(1.6 * max(xb - xa, yb - ya), 0.25 * lado_max, lado_max)))
        else:
            self.region = None                              # perdido: vuelve a buscar en todo el fotograma
        return xy, sc
""")

md("""
## 3. Vertical 1 · Comparativa de modelos de pose (punto 5 del profesor)
Mismo vídeo, mismos fotogramas: 15 tramos de 10 fotogramas repartidos por todo el vídeo, reducidos a 1280 px para no agotar la RAM. Métricas: **FPS**,
**tasa de detección** (% de fotogramas con al menos 5 articulaciones fiables) y **confianza media**.
Se comparan MoveNet (Lightning y Thunder) y YOLO-Pose; la extracción usa `POSE_BACKEND`.
""")
code("""
import torch
from ultralytics import YOLO

MOVENET_URLS = {'lightning': ['https://tfhub.dev/google/movenet/singlepose/lightning/4',
                              'https://www.kaggle.com/models/google/movenet/TensorFlow2/singlepose-lightning/4'],
                'thunder':   ['https://tfhub.dev/google/movenet/singlepose/thunder/4',
                              'https://www.kaggle.com/models/google/movenet/TensorFlow2/singlepose-thunder/4']}
MOVENET_TAM = {'lightning': 192, 'thunder': 256}

def cargar_movenet(variante):
    import tensorflow as tf, tensorflow_hub as hub
    ultimo = None
    for url in MOVENET_URLS[variante]:
        try:
            mod = hub.load(url).signatures['serving_default']
            return (lambda rgb: mod(tf.constant(rgb[None].astype(np.int32)))['output_0'].numpy()[0, 0]), MOVENET_TAM[variante]
        except Exception as e: ultimo = e
    raise RuntimeError(f'No se pudo cargar MoveNet {variante}: {ultimo}')

def leer_frames(path, n):
    # Tramos de 10 fotogramas seguidos repartidos por TODO el vídeo (el seguidor de MoveNet necesita continuidad),
    # para no medir solo el inicio, cuando el nadador puede estar parado en la pared o fuera de cuadro.
    cap = cv2.VideoCapture(path); total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); frames = []
    inicios = np.linspace(0, max(total - 10, 0), max(n // 10, 1)).astype(int)
    for i in inicios:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        for _ in range(10):
            ok, f = cap.read()
            if not ok: break
            if f.shape[1] > MAX_ANCHO:        # 4K -> 1280 px: evita agotar la RAM
                f = cv2.resize(f, (MAX_ANCHO, int(f.shape[0] * MAX_ANCHO / f.shape[1])), interpolation=cv2.INTER_AREA)
            frames.append(f)
    cap.release(); return frames

bench_frames = leer_frames(VIDEO_PATH, N_FRAMES_BENCH)
bh, bw = bench_frames[0].shape[:2]
print(f'{len(bench_frames)} frames para la comparativa ({bw}x{bh})')

def resumen(nombre, params, fps, confs_por_frame):
    c = np.array(confs_por_frame)
    det = (c > CONF_KP).sum(1) >= 5
    return dict(modelo=nombre, params_M=params, fps=round(fps, 1), tasa_deteccion=round(100 * det.mean(), 1),
                conf_media=round(float(c[det].mean()) if det.any() else 0, 3))

def bench_movenet(variante):
    infer, tam = cargar_movenet(variante)
    seg = SeguidorMoveNet(infer, tam, bw, bh); seg(bench_frames[0])     # warm-up
    t0 = time.time(); confs = []
    for k, f in enumerate(bench_frames):
        if k % 10 == 0: seg.region = None                # cada tramo empieza buscando en el fotograma completo
        confs.append(seg(f)[1])
    return resumen(f'movenet_{variante}', None, len(bench_frames) / (time.time() - t0), confs)

def bench_yolo(nombre):
    m = YOLO(nombre); m(bench_frames[0], verbose=False)
    t0 = time.time(); confs = []
    for f in bench_frames:
        r = m(f, verbose=False)[0]
        if r.keypoints is not None and r.keypoints.conf is not None and len(r.boxes):
            confs.append(r.keypoints.conf[int(r.boxes.conf.argmax())].cpu().numpy())
        else: confs.append(np.zeros(17))
    return resumen(nombre.replace('.pt', ''), round(sum(p.numel() for p in m.model.parameters()) / 1e6, 1),
                   len(bench_frames) / (time.time() - t0), confs)

filas = []
for v in ['lightning', 'thunder']:
    try: filas.append(bench_movenet(v)); print(filas[-1])
    except Exception as e: print('omitido movenet', v, e)
for nombre in ['yolov8n-pose.pt', 'yolov8s-pose.pt', 'yolov8m-pose.pt', 'yolo11n-pose.pt', 'yolo11m-pose.pt']:
    try: filas.append(bench_yolo(nombre)); print(filas[-1])
    except Exception as e: print('omitido', nombre, e)

bench = pd.DataFrame(filas)
bench['score'] = bench.tasa_deteccion / 100 * bench.conf_media
bench.to_csv(FIG('comparativa_modelos_pose.csv'), index=False)
display(bench)

if POSE_BACKEND == 'movenet':
    ELEGIDO = f'movenet_{MOVENET_VARIANT}'
    if ELEGIDO not in set(bench.modelo):
        raise RuntimeError(f'{ELEGIDO} no se pudo cargar (mira el mensaje "omitido" de arriba).')
else:
    yolos = bench[bench.modelo.str.startswith('yolo')]
    ELEGIDO = yolos.sort_values('score').iloc[-1].modelo
print('Modelo para la extracción:', ELEGIDO)

fig, ax = plt.subplots(1, 3, figsize=(14, 4))
for a, col, t in zip(ax, ['fps', 'tasa_deteccion', 'conf_media'], ['FPS', 'Tasa de detección (%)', 'Confianza media']):
    a.bar(bench.modelo, bench[col], color=['#2a9d8f' if m == ELEGIDO else '#9aa5b1' for m in bench.modelo])
    a.set_title(t); a.tick_params(axis='x', rotation=45)
plt.tight_layout(); plt.savefig(FIG('fig_comparativa_pose.png'), dpi=150); plt.show()
""", colab_only=True)

md("""
## 4. Vertical 1 · Extracción de keypoints del vídeo completo
Con MoveNet, el seguidor recorta alrededor del nadador en cada fotograma, a resolución completa.
Con YOLO, si hay varias personas, se sigue a la más cercana a su posición anterior.
""")
code("""
cap = cv2.VideoCapture(VIDEO_PATH)
FPS = cap.get(cv2.CAP_PROP_FPS); W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
kps = np.full((N, 17, 2), np.nan); conf = np.zeros((N, 17)); prev_c = None
if POSE_BACKEND == 'movenet':
    infer, tam = cargar_movenet(MOVENET_VARIANT); seguidor = SeguidorMoveNet(infer, tam, W, H)
else:
    model = YOLO(ELEGIDO + '.pt')
t0 = time.time()
for t in range(N):
    ok, f = cap.read()
    if not ok: break
    if POSE_BACKEND == 'movenet':
        kps[t], conf[t] = seguidor(f)
    else:
        r = model(f, verbose=False)[0]
        if r.keypoints is None or r.keypoints.conf is None or len(r.boxes) == 0: continue
        xy = r.keypoints.xy.cpu().numpy(); cf = r.keypoints.conf.cpu().numpy()
        centros = r.boxes.xywh.cpu().numpy()[:, :2]
        if prev_c is None: i = int((r.boxes.conf.cpu().numpy() * r.boxes.xywh.cpu().numpy()[:, 2:].prod(1)).argmax())
        else: i = int(np.linalg.norm(centros - prev_c, axis=1).argmin())
        kps[t], conf[t], prev_c = xy[i], cf[i], centros[i]
    if t % 500 == 0: print(f'{t}/{N}  ({t / max(time.time() - t0, 1e-6):.1f} fps)')
cap.release()
kps, conf = kps[:t+1], conf[:t+1]
np.savez(FIG('keypoints_raw.npz'), kps=kps, conf=conf, fps=FPS, w=W, h=H)
print(f'OK ({ELEGIDO}): {t+1} frames, {FPS:.1f} fps, {W}x{H}, '
      f'frames con >= 5 articulaciones fiables: {100*np.mean((conf > CONF_KP).sum(1) >= 5):.1f}%')
""", colab_only=True)

md("## 5. Limpieza: filtro por confianza, interpolación de huecos cortos y suavizado")
code("""
d = np.load(FIG('keypoints_raw.npz'))
kps, conf, FPS, W, H = d['kps'].copy(), d['conf'], float(d['fps']), int(d['w']), int(d['h'])
T = len(kps); tiempo = np.arange(T) / FPS
kps[conf < CONF_KP] = np.nan

def limpiar(x, fps, max_hueco_s=0.4):
    s = pd.Series(x).interpolate(limit=int(max_hueco_s*fps), limit_area='inside').to_numpy()
    win = max(5, int(fps/5) | 1)                       # ~0.2 s, impar
    out = s.copy(); ok = ~np.isnan(s)
    # suaviza cada tramo continuo
    idx = np.flatnonzero(np.diff(np.r_[0, ok.astype(int), 0]))
    for a, b in zip(idx[::2], idx[1::2]):
        if b - a > win: out[a:b] = savgol_filter(s[a:b], win, 2)
    return out

for j in range(17):
    for c in range(2): kps[:, j, c] = limpiar(kps[:, j, c], FPS)
validez = pd.Series(100*np.mean(~np.isnan(kps[:, :, 0]), 0).round(1),
                    index=['nariz','ojoI','ojoD','orejaI','orejaD','hombroI','hombroD','codoI','codoD','muñecaI','muñecaD',
                           'caderaI','caderaD','rodillaI','rodillaD','tobilloI','tobilloD'])
print('% frames válidos por keypoint tras limpieza:'); print(validez.to_string())
np.save(FIG('keypoints_clean.npy'), kps)
""")

md("""
## 6. Vertical 2 · Features por frame y detección de ciclos de brazada
El ciclo se detecta con la posición de la muñeca **proyectada sobre el eje del cuerpo** (cadera→hombro),
normalizada por la longitud del tronco: no depende del tamaño en píxeles ni de la dirección de nado.
""")
code("""
def ang(a, b, c):                     # ángulo en b (grados)
    v1, v2 = a - b, c - b
    cos = (v1*v2).sum(-1) / (np.linalg.norm(v1, axis=-1)*np.linalg.norm(v2, axis=-1))
    return np.degrees(np.arccos(np.clip(cos, -1, 1)))

hom = (kps[:, LSH] + kps[:, RSH]) / 2; cad = (kps[:, LHIP] + kps[:, RHIP]) / 2
hom = np.where(np.isnan(hom), np.nanmean([kps[:, LSH], kps[:, RSH]], 0), hom)
cad = np.where(np.isnan(cad), np.nanmean([kps[:, LHIP], kps[:, RHIP]], 0), cad)
eje = hom - cad; L_tronco = np.linalg.norm(eje, axis=1)

# --- Filtro de plausibilidad anatómica: descarta detecciones imposibles ---
# Tronco: fuera de [0.5, 2] x la mediana = cadera y hombro mal colocados (p. ej. superpuestos).
L_med = np.nanmedian(L_tronco)
tronco_mal = ~((L_tronco > 0.5 * L_med) & (L_tronco < 2.0 * L_med))
L_tronco[tronco_mal] = np.nan; eje[tronco_mal] = np.nan
u = eje / L_tronco[:, None]
print(f'Fotogramas con tronco implausible descartados: {100*np.mean(tronco_mal & ~np.isnan(hom[:, 0])):.1f}%')

def brazo_ok(sh, el, wr):
    # Brazo y antebrazo entre 0.15 y 1.3 troncos; si no, la detección del brazo no es fiable.
    a = np.linalg.norm(kps[:, el] - kps[:, sh], axis=1) / L_tronco
    b = np.linalg.norm(kps[:, wr] - kps[:, el], axis=1) / L_tronco
    return (a > 0.15) & (a < 1.3) & (b > 0.15) & (b < 1.3)

okI, okD = brazo_ok(LSH, LEL, LWR), brazo_ok(RSH, REL, RWR)
fr = pd.DataFrame({'t': tiempo})
fr['codo_I'] = np.where(okI, ang(kps[:, LSH], kps[:, LEL], kps[:, LWR]), np.nan)
fr['codo_D'] = np.where(okD, ang(kps[:, RSH], kps[:, REL], kps[:, RWR]), np.nan)
fr['munI_eje'] = np.where(okI, ((kps[:, LWR] - kps[:, LSH]) * u).sum(1) / L_tronco, np.nan)
fr['munD_eje'] = np.where(okD, ((kps[:, RWR] - kps[:, RSH]) * u).sum(1) / L_tronco, np.nan)
incl = np.degrees(np.arctan2(np.abs(eje[:, 1]), np.abs(eje[:, 0])))   # 0 = cuerpo horizontal
fr['inclinacion_tronco'] = incl
perp = np.c_[-u[:, 1], u[:, 0]]                                        # perpendicular al cuerpo
fr['tobillo_perp'] = np.nanmean([((kps[:, a] - cad) * perp).sum(1) for a in (LAN, RAN)], 0) / L_tronco
fr.loc[fr.tobillo_perp.abs() > 1.5, 'tobillo_perp'] = np.nan          # tobillo a más de 1.5 troncos del eje: imposible
fr['cadera_x_px'] = cad[:, 0]

# Brazo de referencia: el que más se ve
brazo = 'munD_eje' if fr.munD_eje.notna().mean() >= fr.munI_eje.notna().mean() else 'munI_eje'
# Solo se rellenan huecos cortos: en los tramos sin nadador no se buscan ciclos.
sig = fr[brazo].interpolate(limit=int(0.2*FPS), limit_area='inside').to_numpy()
ok = ~np.isnan(sig)
picos, _ = find_peaks(np.where(ok, sig, np.nanmin(sig)), distance=int(0.6*FPS), prominence=0.3*np.nanstd(sig))
picos = picos[ok[picos]]
print(f'Brazo de referencia: {brazo} | picos (entradas de mano) detectados: {len(picos)}')
print(f'Nadador analizable en {100*ok.mean():.0f}% del vídeo ({ok.sum()/FPS:.1f} s de {len(ok)/FPS:.1f} s)')

plt.figure(figsize=(14, 3)); plt.plot(tiempo, sig, lw=1); plt.plot(tiempo[picos], sig[picos], 'rv')
plt.xlabel('tiempo (s)'); plt.ylabel('muñeca sobre eje (troncos)'); plt.title('Detección de ciclos de brazada')
plt.tight_layout(); plt.savefig(FIG('fig_ciclos.png'), dpi=150); plt.show()
""")

md("""
## 7. Features por ciclo y **eficiencia**
- **SR** (ciclos/min) y brazadas/min (= 2 × SR en crol).
- Si hay calibración: **velocidad**, **DPS** (distancia por ciclo) e **Índice de Brazada SI = v·DPS** (Costill et al., 1985).
- Indicadores técnicos: flexión de codo en el agarre, alcance de brazo, simetría I/D, alineación del tronco y amplitud de patada.
""")
code("""
PPM = (W / METROS_ANCHO_ENCUADRE) if METROS_ANCHO_ENCUADRE else None
filas = []
for k, (a, b) in enumerate(zip(picos[:-1], picos[1:])):
    seg = fr.iloc[a:b]; dur = (b - a) / FPS
    if not (0.6 <= dur <= 3.0) or seg[brazo].isna().mean() > 0.3: continue
    alcI = seg.munI_eje.max() - seg.munI_eje.min(); alcD = seg.munD_eje.max() - seg.munD_eje.min()
    f = dict(ciclo=len(filas)+1, t_inicio_s=round(a/FPS, 2), duracion_s=dur, SR_ciclos_min=60/dur,
             codo_min_I=seg.codo_I.min(), codo_min_D=seg.codo_D.min(),
             alcance_I=alcI, alcance_D=alcD,
             asimetria_brazos_pct=100*abs(alcI-alcD)/np.nanmean([alcI, alcD]),
             inclinacion_tronco=seg.inclinacion_tronco.mean(),
             amplitud_patada=seg.tobillo_perp.max() - seg.tobillo_perp.min())
    if PPM:
        v = abs(np.nanmedian(np.diff(seg.cadera_x_px))) * FPS / PPM     # mediana: robusta a saltos
        f.update(velocidad_m_s=v, DPS_m=v*dur, SI=v*v*dur)
    filas.append(f)
ciclos = pd.DataFrame(filas)
ciclos['brazadas_min'] = 2 * ciclos.SR_ciclos_min
print(f'{len(ciclos)} ciclos válidos')
display(ciclos.round(2).head(10))
display(ciclos.drop(columns=['ciclo', 't_inicio_s']).describe().T[['mean', 'std', 'min', 'max']].round(2))
ciclos.to_csv(FIG('features_por_ciclo.csv'), index=False)
if len(ciclos) < 12:
    print('AVISO: menos de 12 ciclos. Para analizar fatiga usa un vídeo más largo (>= 1 min de nado continuo).')
""")

md("""
## 8. **Fatiga**: en qué momento aparece y por qué
1. Se aprende el patrón "fresco" con los primeros ciclos (`BASELINE_FRAC`) usando **Isolation Forest**.
2. Cada ciclo recibe una **puntuación de anomalía** (cuánto se aleja de su propia técnica fresca).
3. **Inicio de fatiga** = primer ciclo a partir del cual la puntuación supera el umbral de forma sostenida (3 ciclos).
   Se contrasta con detección de punto de cambio (PELT, `ruptures`).
4. **Por qué** = valores **SHAP** del modelo: qué features empujan cada ciclo hacia "fatigado", y cómo cambian respecto a la base.

No se usan a la vez velocidad, DPS y SR, porque son redundantes (v = SR·DPS/60) y SHAP repartiría la importancia entre ellas.
""")
code("""
import shap, ruptures as rpt
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

FEATS = ['SR_ciclos_min', 'codo_min_I', 'codo_min_D', 'alcance_I', 'alcance_D',
         'asimetria_brazos_pct', 'inclinacion_tronco', 'amplitud_patada'] + (['DPS_m'] if 'DPS_m' in ciclos else [])
NOMBRES = {'SR_ciclos_min': 'Frecuencia de ciclo (ciclos/min)', 'codo_min_I': 'Flexión codo izq. en agarre (°)',
           'codo_min_D': 'Flexión codo dcho. en agarre (°)', 'alcance_I': 'Alcance brazo izq. (troncos)',
           'alcance_D': 'Alcance brazo dcho. (troncos)', 'asimetria_brazos_pct': 'Asimetría de brazos (%)',
           'inclinacion_tronco': 'Inclinación del tronco (°)', 'amplitud_patada': 'Amplitud de patada (troncos)',
           'DPS_m': 'Distancia por ciclo (m)'}
X = ciclos[FEATS].copy()
X = X.fillna(X.median())
n_base = max(5, int(BASELINE_FRAC * len(X)))
scaler = StandardScaler().fit(X.iloc[:n_base])
Xs = pd.DataFrame(scaler.transform(X), columns=FEATS)

iso = IsolationForest(n_estimators=500, random_state=42).fit(Xs.iloc[:n_base])
anom = -iso.score_samples(Xs)                       # mayor = más alejado del estado fresco
ciclos['anomalia'] = anom
umbral = np.percentile(anom[:n_base], 95)
suav = pd.Series(anom).rolling(3, min_periods=1).mean().to_numpy()
inicio = None
for i in range(n_base, len(suav) - 2):
    if (suav[i:i+3] > umbral).all(): inicio = i; break
try:
    cp = rpt.Pelt(model='rbf').fit(anom.reshape(-1, 1)).predict(pen=3)
    cambio = [c for c in cp[:-1] if c >= n_base]
except Exception: cambio = []
ciclos['estado'] = np.where((inicio is not None) & (ciclos.index >= (inicio if inicio is not None else 1e9)), 'fatigado', 'fresco')

if inicio is not None:
    t_ini = ciclos.t_inicio_s.iloc[inicio]
    print(f'INICIO DE FATIGA: ciclo {ciclos.ciclo.iloc[inicio]} (t = {t_ini:.1f} s, {100*inicio/len(ciclos):.0f}% del recorrido)')
else:
    t_ini = None; print('No se detecta fatiga sostenida en este vídeo.')
print('Punto(s) de cambio PELT (índice de ciclo):', cambio)

# ---------- SHAP ----------
expl = shap.TreeExplainer(iso)
sv = -expl.shap_values(Xs)                           # signo: positivo = empuja hacia "fatigado/anómalo"
print('Comprobación de signo (corr. suma SHAP vs anomalía, debe ser > 0):', round(np.corrcoef(sv.sum(1), anom)[0, 1], 3))
shap_df = pd.DataFrame(sv, columns=FEATS)
shap_df.to_csv(FIG('shap_por_ciclo.csv'), index=False)
""")

code("""
fig, ax = plt.subplots(2, 1, figsize=(14, 7), sharex=True)
ax[0].plot(ciclos.t_inicio_s, anom, 'o-', label='anomalía por ciclo'); ax[0].plot(ciclos.t_inicio_s, suav, lw=3, alpha=.6, label='media móvil 3')
ax[0].axhline(umbral, ls='--', c='gray', label='umbral (p95 fase fresca)')
ax[0].axvspan(ciclos.t_inicio_s.iloc[0], ciclos.t_inicio_s.iloc[n_base-1], color='green', alpha=.08, label='fase base (fresco)')
if t_ini is not None: ax[0].axvline(t_ini, c='red', lw=2, label=f'inicio fatiga ({t_ini:.1f} s)')
ax[0].legend(loc='upper left'); ax[0].set_ylabel('puntuación de anomalía'); ax[0].set_title(f'{NADADOR}: evolución de la fatiga')
ax[1].plot(ciclos.t_inicio_s, ciclos.SR_ciclos_min, 'o-', label='SR (ciclos/min)')
ax2 = ax[1].twinx(); ax2.plot(ciclos.t_inicio_s, ciclos[['alcance_I', 'alcance_D']].mean(1), 's-', c='C1', label='alcance medio')
ax[1].set_xlabel('tiempo (s)'); ax[1].set_ylabel('SR'); ax2.set_ylabel('alcance (troncos)')
if t_ini is not None: ax[1].axvline(t_ini, c='red', lw=2)
ax[1].legend(loc='upper left'); ax2.legend(loc='upper right')
plt.tight_layout(); plt.savefig(FIG('fig_fatiga_timeline.png'), dpi=150); plt.show()

Xn = X.rename(columns=NOMBRES)
plt.figure(); shap.summary_plot(sv, Xn, show=False); plt.title('SHAP: contribución a la fatiga (todos los ciclos)')
plt.tight_layout(); plt.savefig(FIG('fig_shap_summary.png'), dpi=150, bbox_inches='tight'); plt.show()

if inicio is not None:
    exp_i = shap.Explanation(values=sv[inicio], base_values=float(-np.ravel(expl.expected_value)[0]), data=X.iloc[inicio].values,
                             feature_names=[NOMBRES[f] for f in FEATS])
    plt.figure(); shap.plots.waterfall(exp_i, show=False); plt.title(f'Por qué el ciclo {ciclos.ciclo.iloc[inicio]} ya es fatiga')
    plt.tight_layout(); plt.savefig(FIG('fig_shap_waterfall_inicio.png'), dpi=150, bbox_inches='tight'); plt.show()
""")

md("## 9. Explicación en lenguaje natural para el entrenador")
code("""
def explicar():
    lineas = []
    if inicio is None:
        lineas.append(f'{NADADOR}: no se detecta fatiga sostenida en los {len(ciclos)} ciclos analizados.')
        return lineas
    post = slice(inicio, None)
    imp = shap_df.iloc[post].mean().sort_values(ascending=False)
    lineas.append(f'{NADADOR}: la fatiga aparece en el ciclo {ciclos.ciclo.iloc[inicio]} '
                  f'(t = {t_ini:.1f} s, {100*inicio/len(ciclos):.0f}% del recorrido).')
    lineas.append('Principales causas (contribución SHAP media tras el inicio):')
    for f in imp.index[:4]:
        if imp[f] <= 0: continue
        b, p = X[f].iloc[:n_base].mean(), X[f].iloc[post].mean()
        lineas.append(f'  - {NOMBRES[f]}: {b:.2f} -> {p:.2f} ({100*(p-b)/abs(b):+.0f}%)  [SHAP {imp[f]:+.3f}]')
    return lineas

texto = explicar(); print('\\n'.join(texto))
resumen = dict(nadador=NADADOR, n_ciclos=len(ciclos), n_ciclos_base=n_base, fps=FPS,
               inicio_fatiga_ciclo=None if inicio is None else int(ciclos.ciclo.iloc[inicio]),
               inicio_fatiga_s=t_ini, cambio_pelt=[int(c) for c in cambio], umbral=float(umbral),
               medias=ciclos[FEATS + (['velocidad_m_s', 'SI'] if 'SI' in ciclos else [])].mean().round(3).to_dict(),
               explicacion=texto)
json.dump(resumen, open(FIG('resumen_fatiga.json'), 'w'), ensure_ascii=False, indent=2, default=float)
ciclos.to_csv(FIG('features_por_ciclo.csv'), index=False)
""")

md("""
## 10. Clasificación de estilo (cuando haya datos de varios estilos)
Necesita un CSV con las features por ciclo de **varios estilos y nadadores** (`estilo`, `video` + features).
Se valida con **GroupKFold por vídeo**, para que ciclos del mismo vídeo nunca estén a la vez en train y test (evita el 99.99 % artificial).
""")
code("""
CSV_ESTILOS = os.path.join(os.path.dirname(OUT_DIR), 'ciclos_todos_estilos.csv')
if os.path.exists(CSV_ESTILOS):
    from xgboost import XGBClassifier
    from sklearn.model_selection import GroupKFold, cross_val_predict
    from sklearn.metrics import classification_report
    df = pd.read_csv(CSV_ESTILOS); FE = [c for c in FEATS if c in df]
    y = df.estilo.astype('category'); clf = XGBClassifier(n_estimators=300, max_depth=3, learning_rate=0.05)
    pred = cross_val_predict(clf, df[FE], y.cat.codes, groups=df.video, cv=GroupKFold(5))
    print(classification_report(y.cat.codes, pred, target_names=y.cat.categories))
    clf.fit(df[FE], y.cat.codes); sv_e = shap.TreeExplainer(clf).shap_values(df[FE])
    plt.figure(); shap.summary_plot(sv_e, df[FE], class_names=list(y.cat.categories), show=False)
    plt.savefig(FIG('fig_shap_estilo.png'), dpi=150, bbox_inches='tight'); plt.show()
else:
    print('Sin datos multiestilo todavía: módulo de estilo pendiente.')
""")

md("## 11. Vídeo anotado (para la defensa)")
code("""
SC = min(1.0, MAX_ANCHO / W)          # el vídeo anotado se guarda como máximo a 1280 px de ancho
OW, OH = int(W * SC), int(H * SC); ESC = max(1.0, OW / 1280)
kps_v = kps * SC
cap = cv2.VideoCapture(VIDEO_PATH)
tmp = '/content/anotado_tmp.mp4'
out = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*'mp4v'), FPS, (OW, OH))
ciclo_de_frame = np.full(T, -1)
for i, r in ciclos.iterrows():
    a = int(r.t_inicio_s * FPS); ciclo_de_frame[a:a + int(r.duracion_s * FPS)] = i
for t in range(T):
    ok, f = cap.read()
    if not ok: break
    if SC < 1: f = cv2.resize(f, (OW, OH), interpolation=cv2.INTER_AREA)
    i = ciclo_de_frame[t]; fat = i >= 0 and ciclos.estado.iloc[i] == 'fatigado'
    col = (0, 0, 255) if fat else (0, 200, 0)
    for a, b in SKELETON:
        if not np.isnan(kps_v[t, [a, b]]).any():
            cv2.line(f, tuple(kps_v[t, a].astype(int)), tuple(kps_v[t, b].astype(int)), col, max(3, int(3*ESC)))
    cv2.rectangle(f, (10, 10), (int(560*ESC), int(150*ESC)), (0, 0, 0), -1)
    txt = [f'{NADADOR}  t={t/FPS:5.1f}s']
    if i >= 0:
        r = ciclos.iloc[i]
        cI, cD = fr.codo_I.iloc[t], fr.codo_D.iloc[t]
        txt += [f'Ciclo {int(r.ciclo)} de {len(ciclos)}  SR {r.SR_ciclos_min:4.1f} ciclos/min',
                f'Codo izq {cI:3.0f}  dcho {cD:3.0f} grados  Asimetria {r.asimetria_brazos_pct:3.0f}%'.replace('nan', ' --'),
                ('FATIGA' if fat else 'FRESCO') + f'  (anomalia {r.anomalia:.2f})']
    for k, s in enumerate(txt):
        cv2.putText(f, s, (20, int((40 + 30*k)*ESC)), cv2.FONT_HERSHEY_SIMPLEX, 0.75*ESC, col if k == 3 else (255, 255, 255), 2)
    out.write(f)
cap.release(); out.release()
!ffmpeg -y -loglevel error -i {tmp} -vcodec libx264 -pix_fmt yuv420p "{FIG('video_anotado.mp4')}"
print('Vídeo guardado en', FIG('video_anotado.mp4'))
""", colab_only=True)

md("""
## 12. Listado de resultados
Copia aquí el texto de la sección 9 y las figuras `fig_*.png` en la memoria (Cap. 5).
""")
code("""
for f in sorted(os.listdir(OUT_DIR)): print(f)
""")

nb = nbf.v4.new_notebook()
nb.metadata = {"accelerator": "GPU", "colab": {"provenance": []},
               "kernelspec": {"name": "python3", "display_name": "Python 3"}}
for tipo, src, colab_only in cells:
    c = nbf.v4.new_markdown_cell(src) if tipo == "md" else nbf.v4.new_code_cell(src)
    if colab_only: c.metadata["tags"] = ["colab_only"]
    nb.cells.append(c)
nbf.write(nb, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "notebooks", "StrokeLab_v3_pipeline.ipynb"))
print("ok", len(nb.cells), "celdas")
