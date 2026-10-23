"""Presentación de la defensa del TFM StrokeLab sobre la plantilla UE 2022."""
import copy
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from PIL import Image

FIG = '/home/user/strokelab/memoria/figuras/'
ROJO, NEGRO, GRIS, GRIS_CL, BLANCO = (RGBColor(0xFF, 0x32, 0x28), RGBColor(0x1E, 0x1E, 0x1E), RGBColor(0x50, 0x4B, 0x4B),
                                      RGBColor(0xEE, 0xED, 0xED), RGBColor(0xFF, 0xFF, 0xFF))
AZUL, VERDE, ROSA = RGBColor(0x2D, 0x41, 0xB4), RGBColor(0x23, 0xB4, 0xAA), RGBColor(0xFF, 0xAF, 0xAA)

POST = []
p = Presentation('plantilla_UE_2022.pptx')
lay = {l.name: l for l in p.slide_layouts}

# Conservar solo la portada 1 (foto del campus) y borrar el resto de diapositivas de ejemplo
ids = p.slides._sldIdLst
for sid in list(ids)[1:]:
    p.part.drop_rel(sid.rId)
    ids.remove(sid)


def ph(s, idx):
    for x in s.placeholders:
        if x.placeholder_format.idx == idx:
            return x
    raise KeyError(idx)


def limpiar(s):
    """Quita los marcadores vacíos (si no, PowerPoint muestra «Haga clic para…»)."""
    for x in list(s.placeholders):
        if not x.has_text_frame or not x.text_frame.text.strip():
            x._element.getparent().remove(x._element)


def nueva(nombre, titulo=None, subt=None, notas=None, ancho_titulo=13.5):
    s = p.slides.add_slide(lay[nombre])
    if titulo is not None:
        t = s.shapes.title
        t.text = titulo
        t.width = Inches(min(ancho_titulo, 11.8))
        for q in t.text_frame.paragraphs:
            for r in q.runs:
                r.font.size = Pt(32)
    if subt is not None:
        ph(s, 18).text = subt
        ph(s, 18).width = Inches(13.5)
    if notas:
        s.notes_slide.notes_text_frame.text = notas
    return s


def texto(s, x, y, w, h, parrafos, tam=16, color=NEGRO, negrita=False, alin=PP_ALIGN.LEFT, ancla=MSO_ANCHOR.TOP):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = ancla
    for m in ('margin_left', 'margin_right', 'margin_top', 'margin_bottom'):
        setattr(tf, m, 0)
    if isinstance(parrafos, str):
        parrafos = [parrafos]
    for i, par in enumerate(parrafos):
        q = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        q.alignment = alin
        runs = par if isinstance(par, list) else [(par, {})]
        for txt, op in runs:
            r = q.add_run()
            r.text = txt
            r.font.size = Pt(op.get('tam', tam))
            r.font.bold = op.get('b', negrita)
            r.font.color.rgb = op.get('color', color)
        q.space_after = Pt(op.get('esp', 6) if runs else 6)
    return tb


def caja(s, x, y, w, h, relleno, linea=None):
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    r.fill.solid()
    r.fill.fore_color.rgb = relleno
    if linea is None:
        r.line.fill.background()
    else:
        r.line.color.rgb = linea
        r.line.width = Pt(1)
    r.shadow.inherit = False
    return r


def tarjeta(s, x, y, w, h, cabeza, cuerpo, relleno=GRIS_CL, ccab=ROJO, ccue=NEGRO, num=None):
    caja(s, x, y, w, h, relleno)
    y0 = y + 0.3
    if num:
        texto(s, x + 0.3, y0, w - 0.6, 0.6, num, tam=30, color=ccab, negrita=True)
        y0 += 0.65
    texto(s, x + 0.3, y0, w - 0.6, 0.8, cabeza, tam=18, color=ccab, negrita=True)
    texto(s, x + 0.3, y0 + 0.75, w - 0.6, h - (y0 - y) - 0.95, cuerpo, tam=14, color=ccue)


def cifra(s, x, y, w, numero, etiqueta, cnum=ROJO, cet=NEGRO, tam=40):
    texto(s, x, y, w, 0.85, numero, tam=tam, color=cnum, negrita=True)
    texto(s, x, y + 0.9, w, 0.9, etiqueta, tam=13, color=cet)


def imagen(s, ruta, x, y, w=None, h=None):
    W, H = Image.open(ruta).size
    if w and h:                                   # encajar manteniendo proporción y centrar
        k = min(w / W, h / H)
        ww, hh = W * k, H * k
        return s.shapes.add_picture(ruta, Inches(x + (w - ww) / 2), Inches(y + (h - hh) / 2), Inches(ww), Inches(hh))
    return s.shapes.add_picture(ruta, Inches(x), Inches(y), Inches(w) if w else None, Inches(h) if h else None)


def pie(s, txt, y=7.95):
    texto(s, 0.99, y, 13.5, 0.35, txt, tam=11, color=GRIS)


def tabla(s, x, y, w, filas, anchos, tam=13, alto_fila=0.42, resaltar=()):
    t = s.shapes.add_table(len(filas), len(filas[0]), Inches(x), Inches(y), Inches(w), Inches(alto_fila * len(filas))).table
    for j, a in enumerate(anchos):
        t.columns[j].width = Inches(a)
    for i, fila in enumerate(filas):
        t.rows[i].height = Inches(alto_fila)
        for j, v in enumerate(fila):
            c = t.cell(i, j)
            c.text = str(v)
            c.margin_left = c.margin_right = Inches(0.1)
            c.margin_top = c.margin_bottom = Inches(0.03)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.fill.solid()
            c.fill.fore_color.rgb = ROJO if i == 0 else (ROSA if i in resaltar else (GRIS_CL if i % 2 == 0 else BLANCO))
            for q in c.text_frame.paragraphs:
                for r in q.runs:
                    r.font.size = Pt(tam)
                    r.font.bold = i == 0 or i in resaltar
                    r.font.color.rgb = BLANCO if i == 0 else NEGRO
    return t


# ------------------------------------------------------------------ 1 · Portada
s = p.slides[0]
for x in s.placeholders:
    n = x.name
    if n.startswith('Título'):
        x.text = 'StrokeLab'
    elif n == 'Marcador de texto 7':
        x.text = 'Análisis biomecánico explicable de la técnica y la fatiga en natación'
    elif n == 'Marcador de texto 8':
        x.text = 'Diana Belem Cruz Montesinos'
    elif n == 'Marcador de texto 10':
        x.text = 'Dir.: Francisco Damian Maleno Gonzalez'
    elif n == 'Marcador de texto 9':
        x.text = 'Máster en IA · 24/10/2026'
for x in s.placeholders:
    if x.name in ('Marcador de texto 8', 'Marcador de texto 10', 'Marcador de texto 9'):
        x.left, x.width = Inches(3.99), Inches(3.33)
        x.top = Inches({'Marcador de texto 8': 5.55, 'Marcador de texto 10': 5.95, 'Marcador de texto 9': 6.3}[x.name])
        x.height = Inches(0.36)
        for q in x.text_frame.paragraphs:
            for r in q.runs:
                r.font.size = Pt(12 if x.name == 'Marcador de texto 8' else 10)
s.notes_slide.notes_text_frame.text = (
    'Buenos días. Soy Diana Cruz y presento StrokeLab, un sistema que analiza un vídeo de natación y le dice al '
    'entrenador cómo de eficiente es la brazada, en qué momento aparece la fatiga técnica y por qué. '
    'Todo funciona con una cámara normal y un portátil sin GPU. [≈ 20 s]')

# ------------------------------------------------------------------ 2 · Índice
s = nueva('Indice', 'Índice', notas='Esta es la estructura: el problema, el sistema, cómo lo validé, una demostración con '
          'dos grabaciones de 100 m libre y las conclusiones. [≈ 15 s]', ancho_titulo=6)
s.shapes.title.left, s.shapes.title.top = Inches(1.75), Inches(1.1)
s.shapes.title.height = Inches(1.2)
for r in s.shapes.title.text_frame.paragraphs[0].runs:
    r.font.size = Pt(44)
ph(s, 15).top = Inches(2.6)
ph(s, 15).left = Inches(1.75)
ph(s, 15).text = ''
tf = ph(s, 15).text_frame
for i, (n, t) in enumerate([('01', 'El problema y el objetivo'), ('02', 'StrokeLab: visión + datos tabulares'),
                            ('03', 'Validación y resultados'), ('04', 'Demostración: 100 m libre'),
                            ('05', 'Conclusiones y trabajo futuro')]):
    q = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
    r = q.add_run(); r.text = f'{n}   '; r.font.color.rgb = ROJO; r.font.bold = True; r.font.size = Pt(24)
    r = q.add_run(); r.text = t; r.font.size = Pt(24)
    q.space_after = Pt(14)

# ------------------------------------------------------------------ 3 · Problema
s = nueva('Texto', '¿Cuándo aparece la fatiga y por qué?', 'Hoy el entrenador elige entre el ojo experto y los sensores caros',
          notas='Cuando un nadador se cansa, su técnica cambia antes de que caiga el tiempo: acorta la brazada, sube la '
          'frecuencia, baja el codo. Hoy esto se detecta a ojo, de forma subjetiva, o con sistemas instrumentados '
          '—sensores inerciales, varias cámaras— que son caros y complejos. StrokeLab propone una tercera vía: una sola '
          'cámara convencional y un portátil, y un sistema que no solo detecta la fatiga sino que explica qué variable '
          'la provoca. [≈ 1 min]')
tarjeta(s, 0.99, 3.2, 4.3, 3.3, 'Observación', 'Depende de la experiencia del entrenador. No cuantifica ni deja registro comparable entre sesiones.', num='01')
tarjeta(s, 5.6, 3.2, 4.3, 3.3, 'Sistemas instrumentados', 'Sensores inerciales o varias cámaras: coste elevado y montaje complejo en la piscina.', num='02')
tarjeta(s, 10.21, 3.2, 4.3, 3.3, 'StrokeLab', 'Una cámara convencional y un portátil sin GPU. Mide, detecta el inicio de la fatiga y explica su causa.',
        relleno=ROJO, ccab=BLANCO, ccue=BLANCO, num='03')
limpiar(s)

# ------------------------------------------------------------------ 4 · Objetivo
s = nueva('Texto', 'Objetivo: IA explicable desde un vídeo', 'Indicaciones del director y cómo se cumplen',
          notas='El objetivo general es un sistema de IA explicable que, desde vídeo monocular y en la CPU de un portátil, '
          'cuantifique la técnica, detecte el inicio de la fatiga y explique sus causas. El director marcó cuatro '
          'indicaciones: la explicabilidad es lo más importante, dos verticales de IA —visión y datos tabulares—, '
          'modos diferenciados y optimizar YOLO. La tabla resume cómo responde el sistema a cada una. [≈ 1 min]')
tabla(s, 0.99, 3.15, 14.0, [
    ['Indicación', 'Implementación en StrokeLab'],
    ['La explicabilidad (SHAP) es lo más importante', 'Isolation Forest sobre el estado fresco del propio nadador + TreeSHAP + explicación en texto'],
    ['Dos verticales de IA: visión y tabular', 'Visión: pose 2D (YOLOv8n) y 3D (MotionBERT) · Tabular: variables por ciclo y modelo de fatiga'],
    ['Modos diferenciados (vídeo, tabular, audio)', 'Vídeo y tabular implementados; el audio queda como trabajo futuro'],
    ['Optimizar YOLO (MoveNet, ViTPose)', 'Comparativa en CPU; YOLOv8n elegido; ViTPose como trabajo futuro'],
], [5.2, 8.8], tam=14, alto_fila=0.62)
limpiar(s)

# ------------------------------------------------------------------ 5 · Arquitectura
s = nueva('Texto', 'Dos verticales de IA',
          notas='Esta es la arquitectura. La vertical de visión estima la pose: 17 puntos del cuerpo por fotograma con '
          'YOLOv8n en 2D y MotionBERT en 3D, y los limpia con filtros anatómicos. La vertical tabular divide el nado en '
          'ciclos de brazada, calcula por ciclo la frecuencia, la distancia por ciclo y los ángulos de codo, hombro, '
          'cadera, rodilla y tronco, aprende el patrón fresco del propio nadador con Isolation Forest y explica cada '
          'desviación con SHAP. El resultado llega al entrenador como vídeo anotado, tablas y un texto. [≈ 1 min 15 s]')
imagen(s, FIG + 'arquitectura.png', 2.2, 2.25, 11.6, 6.0)
limpiar(s)

# ------------------------------------------------------------------ 5b · Mapa de algoritmos
s = nueva('Texto', 'Los algoritmos, etapa a etapa', 'Qué se usa en cada paso y con qué se comparó',
          notas='Antes de entrar en detalle, este es el mapa. En cada etapa elegí un algoritmo y lo comparé con '
          'alternativas. La regla fue siempre la misma: que funcione en la CPU de un portátil, con vídeo bajo el agua y '
          'sin etiquetas de fatiga, y que se pueda explicar. En las siguientes diapositivas explico el qué, el cómo y el '
          'porqué de cada uno. [≈ 40 s]')
tabla(s, 0.99, 3.0, 14.0, [
    ['Etapa', 'Algoritmo elegido', 'Tipo', 'Comparado con / descartado'],
    ['Pose 2D', 'YOLOv8n-Pose (CNN de una etapa)', 'Supervisado, preentrenado en COCO', 'YOLO11n, YOLOv8s, MoveNet; HRNet y ViTPose (coste en CPU)'],
    ['Pose 3D', 'MotionBERT-Lite (transformer)', 'Preentrenado en Human3.6M', 'Ángulos 2D: se usan en vista lateral'],
    ['Limpieza', 'Savitzky-Golay + filtros anatómicos', 'Procesado de señal', 'Media móvil (conserva peor los picos)'],
    ['Vista', 'Orientación del tronco por tramos de 60 s', 'Regla', 'Vista indicada a mano por el usuario'],
    ['Ciclos', 'Picos de la mano (lateral) · PCA de la muñeca (frontal)', 'Señal + PCA (no supervisado)', 'Cada muñeca por separado (YOLO copia el brazo)'],
    ['Fatiga', 'Isolation Forest + PELT de contraste', 'No supervisado', 'Red recurrente supervisada'],
    ['Explicación', 'TreeSHAP (valores de Shapley exactos)', 'IA explicable', '—'],
    ['Estilo', 'Reglas biomecánicas', 'Reglas, sin entrenamiento', 'XGBoost y bosque aleatorio'],
], [1.8, 4.5, 3.3, 4.4], tam=12, alto_fila=0.5)
limpiar(s)

# ------------------------------------------------------------------ 5c · Pose 2D: comparativa
s = nueva('Texto', 'Pose 2D: por qué YOLOv8n', 'Ocho modelos considerados; cuatro medidos en el vídeo real',
          notas='Hay tres familias. Los descendentes, como HRNet o ViTPose, detectan primero a la persona y después sus '
          'puntos: son los más precisos en COCO, pero caros en CPU. Los ascendentes, como OpenPose, detectan todos los '
          'puntos y luego los agrupan. Y los de una etapa, como YOLO-Pose, sacan la caja y los 17 puntos en una sola '
          'pasada. La precisión en COCO está medida con personas en tierra, así que no decide sola: medí los candidatos '
          'en mi vídeo subacuático. YOLOv8n detecta igual que YOLOv8s con 3,3 millones de parámetros frente a 11,6 y a 6,6 FPS frente a 3,3, el doble de '
          'velocidad; YOLO11n da resultados equivalentes sin ser más rápido; y frente a MoveNet, que fue mi primera '
          'elección por fluidez, YOLO detecta con el doble de confianza y da 15 ciclos válidos frente a 3. Como el vídeo '
          'anotado se genera después del análisis, la fluidez de MoveNet dejó de importar. [≈ 1 min 15 s]')
tabla(s, 0.99, 3.0, 7.6, [
    ['Modelo', 'Tipo', 'AP COCO', 'Papel'],
    ['ViTPose-G', 'Transformer', '80,9', 'Trabajo futuro'],
    ['HRNet-W48', 'Descendente', '75,5', 'No usado (coste CPU)'],
    ['OpenPose', 'Ascendente', '61,8', 'Referencia'],
    ['YOLOv8s-Pose', 'Una etapa', '60,0', 'Comparado'],
    ['YOLOv8n-Pose', 'Una etapa', '50,4', 'Elegido'],
    ['YOLO11n-Pose', 'Una etapa', '50,0', 'Comparado'],
    ['MoveNet Lightning', 'Una persona', '—', 'Comparado; opción'],
], [2.35, 1.75, 1.2, 2.3], tam=12, alto_fila=0.5, resaltar=(5,))
caja(s, 8.9, 3.0, 6.1, 4.0, GRIS_CL)
texto(s, 9.2, 3.2, 5.5, 0.5, '¿Por qué YOLOv8n? (vídeo real, CPU)', tam=17, color=ROJO, negrita=True)
texto(s, 9.2, 3.8, 5.5, 3.1, [[('•  ' + t, {'tam': 13, 'esp': 8})] for t in [
    'Una sola pasada: caja y 17 puntos a la vez',
    'Frente a YOLOv8s: misma detección (35,6 %) con 3,3 M parámetros frente a 11,6 M y 6,6 FPS frente a 3,3',
    'Frente a YOLO11n: resultados equivalentes (37,6 %, confianza 0,78) sin ser más rápido (6,2 FPS)',
    'Frente a MoveNet: el doble de confianza (0,73-0,77 frente a 0,34-0,37) y 15 ciclos válidos frente a 3',
    'HRNet y ViTPose: mejor AP, pero coste elevado en CPU']])
pie(s, 'AP: precisión media en COCO según las publicaciones originales (personas en tierra). Sin anotaciones propias, la pose bajo el agua se validó con la tarea: frecuencia frente al conteo manual.', y=7.3)
limpiar(s)

# ------------------------------------------------------------------ 6 · Visión
s = nueva('Texto', 'Adaptar la pose humana al agua', 'La pose bajo el agua necesita tres ajustes',
          notas='YOLO se entrenó con personas de pie, no con nadadores horizontales bajo el agua. Tres decisiones lo '
          'adaptan. Primero, el giro: pruebo el fotograma sin girar y girado 90 grados y me quedo con la orientación que '
          'mejor detecta. Segundo, filtros anatómicos: descarto cuerpos imposibles, como un tronco vertical en vista '
          'lateral o la cadera encima del hombro. Tercero, limpio la señal: quito los puntos poco fiables, relleno huecos '
          'cortos y suavizo con Savitzky-Golay, que, a diferencia de una media móvil, no aplasta los picos que luego uso '
          'para contar brazadas. [≈ 50 s]')
tarjeta(s, 0.99, 3.2, 4.3, 3.3, 'Giro ±90°', 'Se prueba el fotograma girado y se conserva la orientación que mejor detecta; las coordenadas vuelven al original.', num='01')
tarjeta(s, 5.6, 3.2, 4.3, 3.3, 'Filtros anatómicos', 'Se descartan troncos girados (> 45°) o verticales en lateral (> 55°), troncos fuera de 0,5-2 × la mediana, segmentos imposibles y codos < 25°.', num='02')
tarjeta(s, 10.21, 3.2, 4.3, 3.3, 'Limpieza de la señal', 'Fuera los puntos con confianza < 0,30; huecos ≤ 0,4 s interpolados; Savitzky-Golay (≈ 0,2 s, grado 2), que conserva los picos mejor que una media móvil.', num='03')
pie(s, 'En GX011614 el filtro de tronco girado quitó el 11,5 % de los fotogramas y la inclinación media del tronco pasó de 42° a 9°.', y=6.8)
limpiar(s)

# ------------------------------------------------------------------ 6b · 3D
s = nueva('Texto', '3D con MotionBERT: cuándo sí y cuándo no', 'Elevación de la pose 2D a 3D con una sola cámara',
          notas='Con una cámara, infinitas posturas 3D dan la misma imagen, así que la profundidad se predice con un '
          'modelo que ha aprendido cómo se mueve el cuerpo: MotionBERT, un transformer preentrenado con Human3.6M, '
          'actores de pie en un laboratorio. Para acercar el nadador a lo que conoce, centro cada fotograma en la pelvis, '
          'giro el tronco a vertical y normalizo la escala; los ángulos no cambian con ese giro. Lo validé comparando '
          'con el 2D en vista lateral: codo, hombro y cadera son coherentes, pero la rodilla sale a 107 grados, como '
          'sentado, cuando la imagen la muestra casi extendida. Decisión: en lateral uso el 2D y guardo el 3D aparte; '
          'de frente o en diagonal, donde el 2D se deforma por la perspectiva, uso el 3D. [≈ 1 min]')
for i, (n, c, d) in enumerate([
        ('1', 'Elevación (lifting)', 'La secuencia de puntos 2D entra en MotionBERT-Lite (transformer DSTformer), que predice la profundidad. ≈ 25 s por vídeo en CPU.'),
        ('2', 'El problema', 'Preentrenado en Human3.6M: actores de pie en un laboratorio, no nadadores horizontales.'),
        ('3', 'La adaptación', 'Centrar en la pelvis, girar el tronco a vertical y normalizar por el tamaño del cuerpo; los ángulos no cambian con el giro.')]):
    y = 3.0 + i * 1.12
    caja(s, 0.99, y, 0.8, 0.8, ROJO)
    texto(s, 0.99, y, 0.8, 0.8, n, tam=24, color=BLANCO, negrita=True, alin=PP_ALIGN.CENTER, ancla=MSO_ANCHOR.MIDDLE)
    texto(s, 2.0, y, 5.6, 0.4, c, tam=16, negrita=True)
    texto(s, 2.0, y + 0.4, 5.6, 0.7, d, tam=12, color=GRIS)
tabla(s, 8.2, 3.0, 6.8, [['Ángulo (I / D)', 'Mediana 2D', 'Mediana 3D', 'Correlación'],
                         ['Codo', '156° / 144°', '158° / 143°', '0,51 / −0,08'],
                         ['Hombro', '90° / 81°', '89° / 92°', '0,69 / 0,71'],
                         ['Cadera', '171° / 172°', '160° / 164°', '0,58 / 0,69'],
                         ['Rodilla', '173° / 173°', '107° / 106°', '0,01 / −0,04']], [1.6, 1.7, 1.7, 1.8], tam=12, alto_fila=0.5, resaltar=(4,))
texto(s, 8.2, 5.6, 6.8, 0.4, 'Vista lateral, secuencia GX011614, 85 fotogramas (Tabla 14 de la memoria)', tam=11, color=GRIS)
caja(s, 0.99, 6.45, 14.0, 1.0, NEGRO)
texto(s, 1.3, 6.45, 13.4, 1.0, [[('Decisión: ', {'b': True, 'color': ROJO, 'tam': 15}),
                                 ('vista lateral → ángulos 2D (el 3D se guarda aparte) · vista frontal u oblicua → ángulos 3D (el 2D se deforma por la perspectiva)', {'color': BLANCO, 'tam': 15})]],
      ancla=MSO_ANCHOR.MIDDLE)
limpiar(s)

# ------------------------------------------------------------------ 6c · Vista y señales de ciclo
s = nueva('Texto', 'Dos vistas, dos señales de brazada', 'El sistema decide la vista y usa la señal que esa vista permite ver',
          notas='Parte de mis vídeos son laterales y parte frontales, y la señal que sirve en uno no sirve en el otro. '
          'Primero, la vista se decide sola: divido el vídeo en tramos de 60 segundos y miro la orientación del tronco; '
          'de lado es casi horizontal y de frente casi vertical. Un fotograma suelto no basta porque YOLO a veces pone '
          'un esqueleto de pie. En lateral cuento brazadas con la profundidad de la mano más profunda: cada máximo es una '
          'brazada. Uso la más profunda porque YOLO copia el brazo visible en el oculto. De frente esa profundidad no se '
          've, así que uso el recorrido de cada muñeca en la dirección en que más se mueve, que saco con PCA, medido en '
          'anchos de hombros. El ritmo es la mediana de los intervalos dentro del rango fisiológico de cada estilo, lo que '
          'lo hace robusto a los huecos. [≈ 1 min 15 s]')
caja(s, 0.99, 3.0, 14.0, 0.95, NEGRO)
texto(s, 1.3, 3.0, 13.4, 0.95, [[('Vista automática: ', {'b': True, 'color': ROJO, 'tam': 14}),
                                ('tramos de 60 s; un tramo es frontal si ≥ 65 % de sus fotogramas tienen el tronco a > 55° de la horizontal '
                                 '(vídeos reales: laterales ≤ 46 %, frontales ≥ 87 %).', {'color': BLANCO, 'tam': 14})]], ancla=MSO_ANCHOR.MIDDLE)
tarjeta(s, 0.99, 4.15, 6.85, 2.55, 'Lateral · profundidad de la mano',
        'Mano más profunda respecto al eje del tronco, en longitudes de tronco; cada máximo es una brazada. '
        'Se toma la más profunda porque YOLO copia el brazo visible en el oculto.')
tarjeta(s, 8.14, 4.15, 6.85, 2.55, 'Frontal · recorrido de la muñeca (PCA)',
        'Recorrido de cada muñeca respecto al centro de los hombros, proyectado en la 1.ª componente principal, en anchos '
        'de hombros. De frente la profundidad no es observable.')
texto(s, 0.99, 6.9, 14.0, 0.8, [[('Común: ', {'b': True, 'tam': 13}),
      ('ritmo = mediana de los intervalos dentro del rango del estilo (crol 0,35-1,0 s; mariposa 0,7-2,0 s; braza 0,7-2,4 s) · '
       'ciclo válido de 0,6-3,0 s con ≤ 30 % de datos ausentes · mínimos y máximos por ciclo con percentiles 10 y 90.', {'tam': 13})]])
limpiar(s)

# ------------------------------------------------------------------ 7 · Ciclos
s = nueva('Texto', 'Contar brazadas con la mano', 'La mano más profunda respecto al eje del cuerpo marca cada brazada',
          notas='Bajo el agua YOLO copia el brazo visible en el oculto: las dos muñecas salen casi idénticas. Por eso no '
          'sigo cada brazo por separado, sino la mano más profunda respecto al eje del cuerpo. Cada pico es una brazada '
          'y en crol dos brazadas forman un ciclo. Lo validé contra mi conteo manual: el error en la frecuencia está '
          'entre el 6,5 y el 8,2 %, en vista lateral y frontal. [≈ 1 min]')
imagen(s, FIG + 'aaron_brazadas.png', 0.99, 3.0, 8.4, 3.5)
tabla(s, 9.8, 3.1, 5.2, [['Secuencia (P1, crol)', 'Manual', 'Sistema', 'Error'],
                         ['GX011614 · lateral', '54,0', '50,5', '−6,5 %'],
                         ['IMG_7207 · frontal', '80,0', '73,9', '−7,6 %'],
                         ['IMG_7215 · frontal', '51,1', '55,2', '+8,2 %']], [2.1, 0.95, 1.1, 1.05], tam=11, alto_fila=0.5)
texto(s, 9.8, 5.3, 5.2, 0.6, 'Frecuencia de ciclo (ciclos/min) frente al conteo manual', tam=11, color=GRIS)
pie(s, 'Gris: intervalo del conteo manual (segundos 30-40). Triángulos: brazadas detectadas.', y=6.7)
limpiar(s)

# ------------------------------------------------------------------ 7b · Por qué Isolation Forest
s = nueva('Texto', '¿Por qué Isolation Forest?', 'Sin etiquetas de fatiga: se busca lo que se aparta del nadador fresco',
          notas='El plan inicial era una red recurrente supervisada, pero para entrenarla hacen falta ciclos etiquetados '
          'como fatigados, y no los hay. Isolation Forest no los necesita: se entrena solo con la fase fresca del propio '
          'nadador. Su idea es sencilla: lo raro se aísla con pocos cortes aleatorios. Si un ciclo queda aislado enseguida, '
          'su puntuación se acerca a 1. Además no supone ninguna distribución, tiene coste lineal y, al ser de árboles, '
          'admite valores SHAP exactos. Antes de entrenar estandarizo cada variable con la media y la desviación de la '
          'fase fresca, y quito las variables redundantes, como la velocidad, que es frecuencia por distancia. '
          '[≈ 1 min]')
caja(s, 0.99, 3.0, 6.6, 1.45, GRIS_CL)
texto(s, 1.3, 3.2, 6.0, 0.4, 'Plan inicial: red recurrente supervisada', tam=16, color=GRIS, negrita=True)
texto(s, 1.3, 3.7, 6.0, 0.7, 'Necesita ciclos etiquetados como «fatigados»: no existen.', tam=14)
caja(s, 0.99, 4.6, 6.6, 2.9, ROJO)
texto(s, 1.3, 4.8, 6.0, 0.4, 'Elegido: Isolation Forest (no supervisado)', tam=16, color=BLANCO, negrita=True)
texto(s, 1.3, 5.35, 6.0, 2.1, [[('•  ' + t, {'tam': 14, 'color': BLANCO, 'esp': 6})] for t in [
    'Se entrena solo con la fase fresca del propio nadador', 'No supone ninguna distribución de los datos',
    'Coste lineal: viable en la CPU', 'Admite SHAP exacto (TreeSHAP)']])
texto(s, 8.0, 3.0, 7.0, 0.4, 'Cómo funciona', tam=18, color=ROJO, negrita=True)
texto(s, 8.0, 3.5, 7.0, 0.7, 'Los ciclos anómalos son escasos y distintos: se aíslan con menos cortes aleatorios que los normales.', tam=14)
caja(s, 8.0, 4.25, 7.0, 0.95, NEGRO)
texto(s, 8.0, 4.25, 7.0, 0.6, [[('s(x, n) = 2^(−E[h(x)] / c(n))', {'tam': 20, 'color': BLANCO, 'b': True})]], alin=PP_ALIGN.CENTER, ancla=MSO_ANCHOR.MIDDLE)
texto(s, 8.0, 4.85, 7.0, 0.35, 'h(x): cortes hasta aislar el ciclo · próximo a 1 = anómalo · < 0,5 = normal', tam=11, color=BLANCO, alin=PP_ALIGN.CENTER)
texto(s, 8.0, 5.4, 7.0, 0.4, 'Configuración', tam=16, negrita=True)
texto(s, 8.0, 5.85, 7.0, 1.7, [[('•  ' + t, {'tam': 13, 'esp': 5})] for t in [
    'Variables estandarizadas con la fase base: z = (x − μ) / σ',
    '500 árboles · fase base = primer 30 % de los ciclos (mín. 5) · mínimo 8 ciclos',
    'Fuera las redundantes: velocidad (= SR · DPS), SI y potencia (∝ v³)']])
limpiar(s)

# ------------------------------------------------------------------ 8 · Fatiga
s = nueva('Texto', 'Fatiga: desviación del patrón fresco', 'Aprendizaje no supervisado: no hacen falta etiquetas de fatiga',
          notas='No hay etiquetas de fatiga, así que planteo el problema como detección de anomalías respecto al propio '
          'nadador. El primer 30 % de sus ciclos es su patrón fresco. Isolation Forest puntúa cada ciclo por lo distinto '
          'que es de ese patrón. El inicio de la fatiga es el primer momento con tres ciclos seguidos por encima del '
          'percentil 95 de la fase fresca, y lo contrasto con el detector de cambios PELT. En la gráfica, con datos '
          'sintéticos y fatiga programada, el sistema la detecta al comienzo de la transición. [≈ 1 min 15 s]')
pasos = [('1', 'Fase fresca', 'Primer 30 % de ciclos del propio nadador'),
         ('2', 'Isolation Forest', 'Puntúa la anomalía de cada ciclo'),
         ('3', 'Inicio de la fatiga', '3 ciclos seguidos sobre el p95 fresco; contraste con PELT'),
         ('4', 'TreeSHAP', 'Qué variable empuja cada ciclo hacia la fatiga')]
for i, (n, c, d) in enumerate(pasos):
    y = 3.05 + i * 1.15
    caja(s, 0.99, y, 0.8, 0.8, ROJO)
    texto(s, 0.99, y, 0.8, 0.8, n, tam=24, color=BLANCO, negrita=True, alin=PP_ALIGN.CENTER, ancla=MSO_ANCHOR.MIDDLE)
    texto(s, 2.0, y, 4.3, 0.4, c, tam=16, negrita=True)
    texto(s, 2.0, y + 0.42, 4.3, 0.6, d, tam=13, color=GRIS)
imagen(s, FIG + 'sintetico_fatiga_timeline.png', 6.7, 2.95, 8.3, 4.5)
pie(s, 'Gráfica: datos sintéticos con fatiga programada (referencia conocida), no un nadador real.', y=7.55)
limpiar(s)

# ------------------------------------------------------------------ 8b · Umbral (sensibilidad) y PELT
s = nueva('Texto', 'Umbral e inicio: elegidos con datos', 'Sensibilidad con fatiga programada entre t = 59 s y t = 81 s',
          notas='Los parámetros del detector los fijé a priori y después comprobé su efecto con datos sintéticos, donde sé '
          'cuándo empieza la fatiga. El percentil del umbral es lo que más pesa. Con el 90 lo detecta todo, pero con un 30 % '
          'de falsas alarmas y antes de tiempo. Con el 99 no hay falsas alarmas, pero pierde un 40 % de las fatigas y llega '
          'tarde. El 95 detecta todas, con un 10 % de falsas alarmas, y sitúa el inicio en el centro de la transición. '
          'Como contraste uso PELT, un detector de cambios que no tiene nada que ver con Isolation Forest: si los dos '
          'coinciden, la detección es más creíble. En la secuencia de 90 s: ciclo 35 frente a ciclo 33. [≈ 1 min]')
tabla(s, 0.99, 3.0, 7.9, [['Percentil del umbral', 'Detección', 'Falsas alarmas', 'Inicio medio'],
                         ['90', '100 %', '30 %', '64,1 s'],
                         ['95 (elegido)', '100 %', '10 %', '70,5 s'],
                         ['99', '60 %', '0 %', '80,5 s']], [2.5, 1.6, 2.0, 1.8], tam=13, alto_fila=0.55, resaltar=(2,))
texto(s, 0.99, 5.35, 7.9, 0.4, 'Fase base 30 % y k = 3 ciclos seguidos (configuración usada).', tam=11, color=GRIS)
texto(s, 0.99, 5.8, 7.9, 1.6, [[('•  ' + t, {'tam': 13, 'esp': 5})] for t in [
    'p90 avisa antes de tiempo; p99 llega tarde y pierde fatigas', 'p95: inicio en 70,5 ± 5,0 s, centro de la transición',
    'La fase base y k influyen menos: subir k quita falsas alarmas y retrasa el aviso']])
caja(s, 9.3, 3.0, 5.7, 4.45, GRIS_CL)
texto(s, 9.6, 3.2, 5.1, 0.5, 'PELT: contraste independiente', tam=17, color=ROJO, negrita=True)
texto(s, 9.6, 3.8, 5.1, 3.6, [[('•  ' + t, {'tam': 13, 'esp': 7})] for t in [
    'Busca los instantes en que cambia la serie de puntuaciones de anomalía',
    'Segmentación exacta en tiempo lineal (poda de candidatos)', 'Coste L2 y penalización β = 2 ln n',
    'Secuencia de 90 s: Isolation Forest ciclo 35 (51,9 s); PELT ciclo 33 (49,4 s)',
    'Si coinciden, la detección se refuerza']])
pie(s, 'Datos sintéticos (Tabla 12 de la memoria): 10 secuencias con fatiga y 10 sin fatiga por configuración.', y=7.6)
limpiar(s)

# ------------------------------------------------------------------ 8c · Cómo funciona SHAP
s = nueva('Texto', 'TreeSHAP: cómo se explica cada ciclo', 'Valores de Shapley exactos sobre el Isolation Forest',
          notas='SHAP viene de la teoría de juegos: reparte de forma justa la puntuación de un ciclo entre sus variables, y '
          'la suma de las partes da la puntuación. Eso permite explicar un ciclo concreto y también todo el nado. Para '
          'modelos de árboles existe TreeSHAP, que calcula los valores exactos, no aproximados, en tiempo polinómico; '
          'por eso fue un criterio al elegir Isolation Forest y el bosque aleatorio. Invierto el signo para que positivo '
          'signifique «acerca a la fatiga», y en cada ejecución compruebo que la suma de SHAP se mueve con la puntuación: '
          '0,999 en la secuencia de 90 s. [≈ 50 s]')
tarjeta(s, 0.99, 3.0, 4.3, 3.6, 'Valores de Shapley',
        'Teoría de juegos: reparten la puntuación entre las variables de forma justa. Aditivos: f(x) = φ0 + Σ φj → explicación de un ciclo y de todo el nado.', num='01')
tarjeta(s, 5.6, 3.0, 4.3, 3.6, 'TreeSHAP',
        'Valores exactos en tiempo polinómico para modelos de árboles: sirve para Isolation Forest y para el bosque aleatorio.', num='02')
tarjeta(s, 10.21, 3.0, 4.3, 3.6, 'Controles',
        'Signo invertido: positivo = acerca a la fatiga. Correlación entre la suma SHAP y la puntuación en cada ejecución (0,999 en la secuencia de 90 s).', num='03')
texto(s, 0.99, 6.85, 14.0, 0.7, [[('Salida para el entrenador: ', {'b': True, 'color': ROJO, 'tam': 14}),
      ('las 4 variables con más contribución y su cambio respecto a la fase fresca. Sin variables redundantes, para que la atribución no se reparta entre medidas equivalentes.', {'tam': 14})]])
limpiar(s)

# ------------------------------------------------------------------ 9 · SHAP
s = nueva('Texto', 'SHAP explica la fatiga', 'Atribución local en el ciclo de inicio (secuencia sintética de 90 s)',
          notas='La parte más importante para el director es la explicación. Para el ciclo en que empieza la fatiga, '
          'TreeSHAP reparte la puntuación de anomalía entre las variables. En la secuencia sintética de 90 s el inicio '
          'se detecta en el ciclo 35, a los 51,9 segundos, y las causas son el alcance del brazo derecho, que pasa de 1,78 a '
          '1,05 troncos, la asimetría de brazos, del 2 al 23 %, y la amplitud de patada. Son justo variables que se '
          'alteraron en la simulación: la explicación es verificable. Uso TreeSHAP porque da los valores exactos en modelos '
          'de árboles, y compruebo en cada ejecución que el signo es coherente. [≈ 1 min 15 s]')
imagen(s, FIG + 'sintetico_shap_waterfall_inicio.png', 0.99, 2.9, 7.0, 5.0)
caja(s, 8.5, 3.05, 6.5, 2.4, NEGRO)
texto(s, 8.8, 3.3, 5.9, 2.0, [
    [('Lo que lee el entrenador', {'b': True, 'color': ROJO, 'tam': 16})],
    [('Inicio de la fatiga en el ciclo 35 (t = 51,9 s). Causas: alcance del brazo derecho (1,78 → 1,05 troncos), '
      'asimetría de brazos (2 % → 23 %) y amplitud de patada (0,31 → 0,21 troncos).', {'color': BLANCO, 'tam': 15})]])
texto(s, 8.5, 5.8, 6.5, 1.0, 'Las variables señaladas coinciden con las alteradas en la simulación: la explicación es verificable.',
      tam=14, color=NEGRO, negrita=True)
texto(s, 8.5, 6.55, 6.5, 1.0, [[('Por qué TreeSHAP: ', {'b': True, 'color': ROJO, 'tam': 13}),
      ('valores de Shapley exactos para modelos de árboles (como Isolation Forest); el signo se comprueba en cada ejecución (correlación 0,999).', {'tam': 13})]])
pie(s, 'Datos sintéticos de referencia conocida (memoria, Figura 7 y apartado 4.6.2).', y=7.95)
limpiar(s)

# ------------------------------------------------------------------ 9b · Estilo
s = nueva('Texto', 'Estilo: del modelo supervisado a reglas', 'El 100 % con datos sintéticos no se mantenía con nadadores reales',
          notas='Para el estilo empecé con XGBoost y lo cambié por un bosque aleatorio, más sencillo y con SHAP exacto. '
          'Lo validé por vídeo, con GroupKFold, para no mezclar ventanas del mismo vídeo en entrenamiento y prueba. Con '
          'datos sintéticos acertaba el 100 %. Con vídeos reales, dejando un vídeo fuera, el 45,5 %, apenas por encima del '
          '36,4 % de decir siempre la clase mayoritaria; y dejando fuera a un participante, el 9,1 %: había aprendido a '
          'reconocer al nadador, no el estilo. Por eso pasé a reglas que salen de la definición de cada estilo: si las '
          'manos se mueven a la vez o alternas, y la altura de la cabeza. Aciertan la familia en 12 de 13 vídeos, que es '
          'lo que necesito para contar ciclos. Los umbrales los fijé con esos vídeos, así que el dato es optimista. '
          '[≈ 1 min]')
tarjeta(s, 0.99, 3.0, 4.3, 3.9, 'XGBoost', 'Boosting: árboles en secuencia que corrigen al anterior. Se sustituyó por un modelo más sencillo y con SHAP exacto.', num='01')
tarjeta(s, 5.6, 3.0, 4.3, 3.9, 'Bosque aleatorio',
        '300 árboles, ventanas de 4 s, GroupKFold por vídeo. Sintéticos: 100 %. Reales: 45,5 % dejando un vídeo fuera '
        '(base 36,4 %) y 9,1 % dejando fuera un participante → aprendía al nadador.', num='02')
tarjeta(s, 10.21, 3.0, 4.3, 3.9, 'Reglas biomecánicas',
        'Sin entrenamiento. Correlación de las manos (0,65 lateral / 0,20 frontal) → alternos o simultáneos; nariz '
        'respecto a hombros → braza o espalda. Familia 12/13 reales; estilo 9/13; sintéticos 81 %.',
        relleno=ROJO, ccab=BLANCO, ccue=BLANCO, num='03')
pie(s, 'Umbrales fijados con los vídeos reales: la exactitud real es optimista. De frente no distingue mariposa de braza. La familia basta para contar ciclos (2 o 1 brazadas).', y=7.15)
limpiar(s)

# ------------------------------------------------------------------ 9c · Decisiones
s = nueva('Texto', 'Qué cambió y por qué', 'Cambios respecto al planteamiento inicial (memoria, apartado 5.2)',
          notas='Esta tabla resume las decisiones. Ninguna se tomó por preferencia: cada cambio responde a algo que medí. '
          'La más importante para mí es la de la validación: una versión anterior daba un 99,99 % de exactitud por fotograma '
          'y era fuga de datos; desde entonces todo se valida por vídeo o por participante. [≈ 45 s]')
tabla(s, 0.99, 3.0, 14.0, [
    ['Planteamiento inicial', 'Decisión final', 'Motivo'],
    ['MoveNet', 'YOLOv8n-Pose', 'Doble de confianza y cinco veces más ciclos válidos bajo el agua'],
    ['Solo vista lateral', 'Lateral y frontal, vista automática por tramos', 'Parte de los vídeos es frontal: la profundidad de la mano no se ve'],
    ['Red recurrente supervisada', 'Isolation Forest no supervisado', 'Sin etiquetas de fatiga; admite SHAP exacto'],
    ['XGBoost', 'Bosque aleatorio → reglas biomecánicas', 'El modelo supervisado aprendía al nadador, no el estilo'],
    ['Validación por fotograma', 'Validación por vídeo (GroupKFold)', 'El 99,99 % de una versión anterior era fuga de datos'],
    ['Potencia en vatios', 'Indicadores cinemáticos', 'La potencia depende de CD y A, no medibles desde vídeo'],
    ['Sensores inerciales', 'Solo vídeo', 'No se dispuso de sensores (trabajo futuro)'],
], [3.5, 4.6, 5.9], tam=13, alto_fila=0.55, resaltar=(5,))
limpiar(s)

# ------------------------------------------------------------------ 10 · Resultados reales
s = nueva('Texto', 'Resultados con nadadores reales', '17 secuencias · 4 participantes · 4 estilos',
          notas='Con vídeo real analicé 17 secuencias de 4 participantes en 4 estilos: 6,6 minutos grabados, de los que '
          '2,2 minutos fueron analizables, con 95 ciclos válidos. La frecuencia se aproxima al conteo manual con un '
          'error del 6,5 al 8,2 %. La vista automática clasificó bien las 17 secuencias, aunque el umbral se fijó con ellas, y la familia del estilo '
          'en 12 de 13. Las sesiones de pasadas cortas no dieron fatiga, y tampoco falsas alarmas: es lo esperable, '
          'porque son pasadas a ritmo técnico con descansos. El nadador fue analizable en el 34 % del tiempo: la detección '
          'bajo el agua es la principal limitación. [≈ 1 min]')
items = [('95', 'ciclos válidos de 6,6 min grabados (2,2 min analizables)'),
         ('6,5-8,2 %', 'error de la frecuencia frente al conteo manual'),
         ('17/17', 'secuencias reales con la vista de cámara bien clasificada (umbral fijado con ellas)'),
         ('12/13', 'secuencias con la familia del estilo correcta (reglas biomecánicas)'),
         ('0', 'falsas alarmas de fatiga en 3 sesiones de pasadas cortas'),
         ('34 %', 'del tiempo grabado con el nadador analizable: la detección es el cuello de botella')]
for i, (n, e) in enumerate(items):
    x = 0.99 + (i % 3) * 4.7
    y = 3.05 + (i // 3) * 2.35
    caja(s, x, y, 4.4, 2.1, GRIS_CL if i != 0 else ROJO)
    cifra(s, x + 0.3, y + 0.2, 3.9, n, e, cnum=BLANCO if i == 0 else ROJO, cet=BLANCO if i == 0 else NEGRO, tam=36)
limpiar(s)

# ------------------------------------------------------------------ 11 · Sintéticos
s = nueva('Texto', 'Validación con referencia conocida', 'Datos sintéticos: se sabe exactamente cuándo empieza la fatiga',
          notas='Como no tengo una referencia real de fatiga, construí un generador de datos sintéticos en el que sé la '
          'verdad: la frecuencia, la velocidad y el momento exacto en que empieza la fatiga. Con él, el error mediano es '
          'del 4,7 % en frecuencia, del 1,3 % en velocidad y del 4,3 % en distancia por ciclo. El detector encuentra la '
          'fatiga en el 100 % de los casos con un 10 % de falsas alarmas, y en tiempo real detecta 10 de 10 sin falsas '
          'alarmas. Son datos sintéticos y así los presento: sirven para comprobar que el método funciona cuando la '
          'verdad se conoce. [≈ 1 min]')
for i, (n, e) in enumerate([('4,7 %', 'error mediano en la frecuencia de ciclo'), ('1,3 %', 'error mediano en la velocidad'),
                            ('4,3 %', 'error mediano en la distancia por ciclo')]):
    cifra(s, 0.99 + i * 2.6, 3.2, 2.4, n, e, tam=34)
caja(s, 0.99, 5.3, 7.4, 2.2, ROJO)
texto(s, 1.3, 5.5, 3.3, 1.9, [[('100 %', {'tam': 40, 'b': True, 'color': BLANCO})], [('detección de la fatiga · 10 % de falsas alarmas', {'tam': 13, 'color': BLANCO})]])
texto(s, 4.8, 5.5, 3.4, 1.9, [[('10/10', {'tam': 40, 'b': True, 'color': BLANCO})], [('en tiempo real, sin falsas alarmas', {'tam': 13, 'color': BLANCO})]])
imagen(s, FIG + 'caso_verdad_vs_sistema.png', 8.9, 2.9, 6.1, 4.7)
pie(s, 'Datos sintéticos (generador con referencia conocida), presentados como tales.', y=7.75)
limpiar(s)

# ------------------------------------------------------------------ 12 · Al entrenador
s = nueva('Texto', 'Del análisis al entrenador', 'Vídeo anotado y modo en tiempo real',
          notas='El resultado no es un número suelto. El vídeo anotado muestra en cada momento si el nadador está fresco o '
          'fatigado, el ciclo y la frecuencia, y una barra con la anomalía de cada ciclo y el umbral. El modo en tiempo '
          'real hace lo mismo mientras se reproduce el vídeo o la cámara, y muestra las causas de SHAP en directo. '
          'Además, el sistema decide solo la vista y la familia del estilo, y procesa listas de vídeos por lotes. [≈ 45 s]')
imagen(s, FIG + 'panel_video.png', 0.99, 2.95, 8.0, 4.5)
for i, (c, d) in enumerate([('Estado por ciclo', 'FRESCO / FATIGA, ciclo y frecuencia sobre el vídeo'),
                            ('Barra de anomalía', 'Puntuación de cada ciclo, umbral e inicio de la fatiga'),
                            ('Tiempo real', 'Calibra con los 10 primeros ciclos y explica con SHAP en directo'),
                            ('Automático', 'Vista de cámara, familia del estilo y lotes de vídeos')]):
    y = 3.0 + i * 1.12
    texto(s, 9.5, y, 5.5, 0.4, c, tam=16, color=ROJO, negrita=True)
    texto(s, 9.5, y + 0.42, 5.5, 0.6, d, tam=13)
pie(s, 'Captura del vídeo anotado sobre datos sintéticos.', y=7.55)
limpiar(s)

# ------------------------------------------------------------------ 12b · Demostración
s = nueva('Texto', 'Demostración: 100 m libre', 'Dos grabaciones nuevas analizadas con StrokeLab (GoPro, 60 fps)',
          notas='Para terminar, una demostración con dos grabaciones de 100 m libre, una suave y otra rápida, hechas después '
          'de entregar la memoria; no forman parte de sus resultados. [Reproducir el vídeo anotado del 100 suave.] '
          'En el suave el sistema decidió solo que la vista era lateral y el estilo crol, y obtuvo 20 ciclos válidos a 56 '
          'ciclos por minuto. En el rápido la cámara ve al nadador de frente u oblicuo gran parte del tiempo: en lateral '
          'solo salían 2 ciclos válidos y, indicando la vista frontal, 39 ciclos a 54 ciclos por minuto. En ninguno hay '
          'fatiga sostenida declarada. En el rápido, sin embargo, la puntuación de anomalía sube al final: los dos últimos ciclos son los más anómalos de todo el vídeo, pero la regla exige tres ciclos seguidos y el vídeo termina antes. La frecuencia de los dos es parecida; sin un conteo manual no '
          'afirmo cuál es más precisa. Es justo lo que dice la memoria: la vista y la detección condicionan el análisis. '
          '[≈ 1 min 30 s] NO mostrar los ángulos de cadera y rodilla del suave: las piernas se detectan mal en este vídeo.')
for k, (x, cab, its) in enumerate([
        (0.99, '100 suave', ['Vista lateral y estilo crol detectados automáticamente', '20 ciclos válidos · 42,5 s analizables de 86 s',
                             '56 ciclos/min de media', 'Sin fatiga sostenida']),
        (8.1, '100 rápido', ['Vista frontal u oblicua: indicada manualmente (en lateral, solo 2 ciclos)', '39 ciclos válidos · 76 s analizables de 106 s',
                             '54 ciclos/min de media', 'Sin fatiga declarada: los 2 últimos ciclos son los más anómalos del vídeo (la regla exige 3 seguidos)'])]):
    caja(s, x, 3.0, 6.9, 2.3, GRIS_CL, linea=RGBColor(0xB4, 0xB4, 0xB4))
    texto(s, x, 3.0, 6.9, 2.3, [[('Insertar aquí el vídeo anotado', {'tam': 13, 'color': GRIS})],
                                [('Insertar → Vídeo → Este dispositivo', {'tam': 11, 'color': GRIS})]], alin=PP_ALIGN.CENTER, ancla=MSO_ANCHOR.MIDDLE)
    texto(s, x, 5.45, 6.9, 0.45, cab, tam=18, color=ROJO, negrita=True)
    texto(s, x, 5.95, 6.9, 1.5, [[('•  ' + t, {'tam': 13, 'esp': 4})] for t in its])
pie(s, 'Grabaciones posteriores a la entrega, solo como demostración; frecuencia sin validar con conteo manual.', y=7.6)
limpiar(s)

# ------------------------------------------------------------------ 13 · Posterior a la entrega
POST.append(len(p.slides._sldIdLst))
s = nueva('Texto', 'Tras la entrega: ajuste fino de la pose',
          '405 imágenes reales anotadas · validación cruzada por grabación',
          notas='Después de entregar quise atacar la principal limitación, la detección bajo el agua. Usé 405 imágenes '
          'reales de nadadores anotadas, públicas, y evalué con validación cruzada de cuatro pliegues separando por '
          'grabación para que no haya fuga de datos. El modelo ajustado detecta al nadador en el 78 % de las imágenes '
          'frente al 47 % del original, y el OKS sube de 0,10 a 0,40. Probé también modelos más grandes y datos '
          'sintéticos: no mejoran, lo que confirma que el límite son los datos reales del dominio. Y aplicado a mis '
          'vídeos aumenta el tiempo analizable un 26 %, pero la frecuencia no mejora: las reglas posteriores están '
          'calibradas con el modelo original y hay que recalibrarlas. Por eso el sistema de la memoria sigue con el '
          'modelo original. [≈ 1 min 30 s]')
cd = CategoryChartData()
cd.categories = ['Detección', 'PCK@0,1', 'PCK@0,2']
cd.add_series('Original (con giro)', (47, 9, 15))
cd.add_series('Ajustado', (78, 37, 56))
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.99), Inches(3.2), Inches(7.6), Inches(4.4), cd)
ch = gf.chart
ch.has_legend = True
ch.legend.position = XL_LEGEND_POSITION.TOP
ch.legend.include_in_layout = False
ch.legend.font.size = Pt(12)
ch.value_axis.maximum_scale = 100
ch.value_axis.has_major_gridlines = True
ch.value_axis.major_gridlines.format.line.color.rgb = RGBColor(0xDD, 0xDD, 0xDD)
ch.value_axis.tick_labels.font.size = Pt(11)
ch.category_axis.tick_labels.font.size = Pt(12)
for ser, col in zip(ch.plots[0].series, (RGBColor(0xB4, 0xB4, 0xB4), ROJO)):
    ser.format.fill.solid(); ser.format.fill.fore_color.rgb = col
pl = ch.plots[0]
pl.has_data_labels = True
pl.data_labels.number_format = '0"%"'
pl.data_labels.number_format_is_linked = False
pl.data_labels.font.size = Pt(12)
pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
pl.gap_width = 80
for i, (c, d) in enumerate([('OKS 0,10 → 0,40', 'Precisión de los puntos ×4 en imágenes nunca vistas'),
                            ('n ≈ s ≈ m', 'Modelos más grandes no mejoran: el límite son los datos'),
                            ('+ sintéticos = igual', 'SwimXYZ (777 imágenes) no mejora la prueba real'),
                            ('Vídeos propios', '+26 % tiempo analizable; la frecuencia no mejora → recalibrar')]):
    y = 3.0 + i * 1.15
    texto(s, 9.1, y, 5.9, 0.4, c, tam=16, color=ROJO, negrita=True)
    texto(s, 9.1, y + 0.42, 5.9, 0.6, d, tam=13)
pie(s, 'Roboflow «Deep Dive Pose Technique» (CC BY 4.0). Media de 4 pliegues. Resultados posteriores a la entrega de la memoria.', y=7.75)
limpiar(s)

# ------------------------------------------------------------------ 14 · Limitaciones y futuro
s = nueva('Texto', 'Limitaciones y trabajo futuro', 'La debilidad está en los datos, no en la arquitectura',
          notas='Las limitaciones son claras y las identifiqué con datos. Faltan grabaciones de nado continuo y una '
          'referencia fisiológica, así que la fatiga real no está validada todavía. El nadador solo es analizable el 34 % '
          'del tiempo y en vista lateral el modelo copia el brazo oculto. Con una cámara, los ángulos son proyecciones y '
          'el 3D falla en las piernas. El trabajo futuro sale directamente de ellas: series largas con lactato, esfuerzo '
          'percibido y valoración del entrenador; anotar fotogramas propios para medir OKS, PCK y mAP; ajustar la pose '
          'con SwimXYZ y datos propios; y ampliar con audio, sensores inerciales y una interfaz. [≈ 1 min]')
for k, (cab, its, x, rel) in enumerate([
        ('Limitaciones', ['Pocos datos reales y sin referencia fisiológica de la fatiga',
                          'Detección parcial: nadador analizable el 34 % del tiempo',
                          'Vista lateral: brazos y piernas de cada lado poco distinguibles',
                          'Una sola cámara: ángulos 2D proyectados; 3D poco fiable en piernas',
                          'Umbrales de vista y estilo fijados con los mismos vídeos'], 0.99, GRIS_CL),
        ('Trabajo futuro', ['Series largas de nado continuo con lactato, esfuerzo percibido y valoración experta',
                            'Anotar fotogramas propios: OKS, PCK y mAP con datos propios',
                            'Ajuste fino de la pose con SwimXYZ y fotogramas propios; ViTPose con GPU',
                            'Modo audio, sensores inerciales e interfaz para el entrenador'], 8.0, ROJO)]):
    caja(s, x, 3.05, 7.0, 4.5, rel)
    col = NEGRO if rel == GRIS_CL else BLANCO
    texto(s, x + 0.35, 3.3, 6.3, 0.5, cab, tam=20, color=ROJO if rel == GRIS_CL else BLANCO, negrita=True)
    texto(s, x + 0.35, 3.95, 6.3, 3.5, [[('•  ' + t, {'color': col, 'tam': 14, 'esp': 10})] for t in its])
limpiar(s)

# ------------------------------------------------------------------ 15 · Conclusiones
s = nueva('Texto', 'Conclusiones', '7 objetivos cumplidos y 2 parciales',
          notas='En resumen: siete objetivos cumplidos y dos parciales. Los parciales son honestos: la fatiga está validada '
          'con datos sintéticos y en tiempo real, pero falta la validación fisiológica con nadadores reales; y el '
          'clasificador de estilo supervisado no generalizaba, por eso lo sustituí por reglas biomecánicas. La lección '
          'principal del trabajo es que la calidad de los datos pesa más que el modelo: detecté una exactitud del 99,99 % '
          'que era fuga de datos y, desde entonces, contrasté cada resultado con una referencia. Gracias. [≈ 1 min]')
obj = [('OE1', 'Selección del modelo de pose', 'C'), ('OE2', 'Elevación a 3D', 'C*'), ('OE3', 'Ciclos de brazada', 'C'),
       ('OE4', 'Variables por ciclo', 'C'), ('OE5', 'Inicio de la fatiga', 'P'), ('OE6', 'Atribución con SHAP', 'C'),
       ('OE7', 'Clasificación del estilo', 'P'), ('OE8', 'Vídeo anotado y tiempo real', 'C'), ('OE9', 'Evaluación con datos sintéticos', 'C')]
for i, (c, d, g) in enumerate(obj):
    x = 0.99 + (i % 3) * 3.15
    y = 3.05 + (i // 3) * 1.45
    caja(s, x, y, 2.95, 1.25, ROJO if g.startswith('C') else NEGRO)
    texto(s, x + 0.2, y + 0.15, 2.6, 0.4, f'{c} · {"Cumplido" if g == "C" else ("Cumplido*" if g == "C*" else "Parcial")}', tam=12, color=BLANCO, negrita=True)
    texto(s, x + 0.2, y + 0.55, 2.6, 0.6, d, tam=13, color=BLANCO)
texto(s, 10.7, 3.05, 4.3, 4.2, [
    [('La calidad de los datos pesa más que el modelo.', {'tam': 20, 'b': True, 'color': ROJO, 'esp': 14})],
    [('Cada resultado se contrastó con una referencia: conteo manual o datos sintéticos con la verdad conocida.', {'tam': 14})]])
pie(s, '* Cumplido con limitaciones (3D válido en codo y cadera, no en rodilla).', y=7.55)
limpiar(s)

# ================================================================== VERSIÓN DE 12 DIAPOSITIVAS (defensa)
# ------------------------------------------------------------------ D2 · Problema y objetivo
s = nueva('Texto', 'Problema y objetivo', '¿Cuándo aparece la fatiga técnica y por qué?',
          notas='Cuando un nadador se cansa, su técnica cambia antes de que caiga el tiempo: acorta la brazada, sube la '
          'frecuencia, baja el codo. Hoy esto se ve a ojo o con sensores y varias cámaras, que son caros. Mi objetivo es '
          'una tercera vía: un sistema de IA explicable que, con una cámara y un portátil sin GPU, mida la técnica, '
          'detecte el inicio de la fatiga y diga qué variable la provoca. El director pidió que la explicabilidad fuera '
          'lo más importante y que hubiera dos verticales de IA: visión y datos tabulares. [≈ 1 min]')
tarjeta(s, 0.99, 3.0, 4.3, 2.75, 'Observación', 'Depende del ojo del entrenador: no cuantifica ni deja registro comparable.', num='01')
tarjeta(s, 5.6, 3.0, 4.3, 2.75, 'Sistemas instrumentados', 'Sensores inerciales o varias cámaras: caros y de montaje complejo.', num='02')
tarjeta(s, 10.21, 3.0, 4.3, 2.75, 'StrokeLab', 'Una cámara y un portátil sin GPU: mide, detecta el inicio de la fatiga y explica su causa.',
        relleno=ROJO, ccab=BLANCO, ccue=BLANCO, num='03')
caja(s, 0.99, 6.0, 13.52, 1.4, NEGRO)
texto(s, 1.3, 6.0, 13.0, 1.4, [[('Objetivo: ', {'b': True, 'color': ROJO, 'tam': 15}),
      ('IA explicable desde vídeo monocular en CPU. Indicaciones del director: la explicabilidad (SHAP) es lo más '
       'importante · dos verticales de IA, visión y tabular · optimizar YOLO frente a MoveNet y ViTPose.', {'color': BLANCO, 'tam': 15})]],
      ancla=MSO_ANCHOR.MIDDLE)
limpiar(s)

# ------------------------------------------------------------------ D3 · Algoritmos
s = nueva('Texto', 'Algoritmos: qué y por qué', 'Vertical de visión (pose) → vertical tabular (ciclos, fatiga, SHAP)',
          notas='Este es el sistema entero, etapa a etapa. La regla para elegir fue siempre la misma: que funcione en la '
          'CPU de un portátil, con vídeo bajo el agua y sin etiquetas de fatiga, y que se pueda explicar. En la columna de '
          'la derecha está el porqué de cada elección frente a la alternativa. Las dos verticales: la visión saca los '
          'puntos del cuerpo; la tabular convierte esos puntos en variables por ciclo, detecta la fatiga y la explica. '
          '[≈ 1 min 15 s]')
tabla(s, 0.99, 3.0, 14.0, [
    ['Etapa', 'Algoritmo elegido', 'Alternativa comparada', 'Por qué'],
    ['Pose 2D', 'YOLOv8n-Pose (CNN, una etapa)', 'YOLO11n, YOLOv8s, MoveNet, HRNet, ViTPose', 'Detecta como v8s (35,6 %) con 3,3 M parámetros frente a 11,6 M; doble de confianza que MoveNet'],
    ['Pose 3D', 'MotionBERT-Lite (transformer)', 'Ángulos 2D', 'Solo de frente: en lateral falla la rodilla (107° frente a 173°)'],
    ['Vista', 'Orientación del tronco, tramos de 60 s', 'Vista indicada a mano', 'Hay vídeos laterales y frontales, incluso en el mismo vídeo'],
    ['Ciclos', 'Picos de la mano (lateral) · PCA (frontal)', 'Cada muñeca por separado', 'YOLO copia el brazo visible en el oculto'],
    ['Fatiga', 'Isolation Forest + PELT', 'Red recurrente supervisada', 'No hay etiquetas de fatiga; coste lineal; SHAP exacto'],
    ['Explicación', 'TreeSHAP', '—', 'Valores de Shapley exactos para modelos de árboles'],
    ['Estilo', 'Reglas biomecánicas', 'XGBoost, bosque aleatorio', 'El supervisado aprendía al nadador: 9,1 % con un nadador nuevo'],
], [1.6, 3.9, 3.6, 4.9], tam=12, alto_fila=0.55, resaltar=(5,))
limpiar(s)

# ------------------------------------------------------------------ D4 · Visión
s = nueva('Texto', 'Visión: pose bajo el agua', 'Modelos medidos en el vídeo real (GX011614, CPU de 4 hilos)',
          notas='Comparé los modelos en mi propio vídeo subacuático, porque la precisión publicada en COCO es con personas '
          'en tierra. YOLOv8n detecta lo mismo que YOLOv8s con 3,3 millones de parámetros frente a 11,6 y a 6,6 FPS frente a 3,3; '
          'YOLO11n queda equivalente sin ser más rápido. MoveNet fue mi primera elección por fluidez, pero YOLO detecta con '
          'el doble de confianza y da 15 ciclos válidos frente a 3; HRNet y ViTPose son más precisos en COCO pero caros en '
          'CPU. Como YOLO se entrenó con personas de pie, lo adapté: giro el fotograma 90 grados si detecta mejor, descarto '
          'cuerpos imposibles y suavizo con Savitzky-Golay. El 3D de MotionBERT pone la rodilla doblada como si el '
          'nadador estuviera sentado, así que en lateral uso el 2D y el 3D solo de frente. [≈ 1 min 30 s]')
tabla(s, 0.99, 3.0, 7.9, [['Modelo', 'Parám. (M)', 'FPS', 'Detección', 'Confianza'],
                         ['YOLOv8n (elegido)', '3,3', '6,6', '35,6 %', '0,76'],
                         ['YOLO11n', '2,9', '6,2', '37,6 %', '0,78'],
                         ['YOLOv8s', '11,6', '3,3', '35,6 %', '0,74'],
                         ['MoveNet Lightning', '—', '—', '35-48 %*', '0,34-0,37*']], [2.6, 1.3, 0.9, 1.5, 1.6], tam=13, alto_fila=0.5, resaltar=(1,))
texto(s, 0.99, 5.6, 7.9, 1.8, [[('•  ' + t, {'tam': 13, 'esp': 5})] for t in [
    'Frente a MoveNet (vídeo subacuático): doble de confianza y 15 ciclos válidos frente a 3',
    'HRNet (AP 75,5) y ViTPose (80,9): más precisos en COCO, coste elevado en CPU']])
caja(s, 9.3, 3.0, 5.7, 4.4, GRIS_CL)
texto(s, 9.6, 3.2, 5.1, 0.5, 'Adaptación al agua', tam=17, color=ROJO, negrita=True)
texto(s, 9.6, 3.8, 5.1, 3.5, [[('•  ' + t, {'tam': 13, 'esp': 7})] for t in [
    'Giro ±90° del fotograma si detecta mejor (YOLO se entrenó con personas de pie)',
    'Filtros anatómicos: tronco girado o vertical, segmentos imposibles, codos < 25°',
    'Savitzky-Golay: suaviza sin aplastar los picos (frente a una media móvil)',
    '3D con MotionBERT solo de frente: en lateral la rodilla sale a 107° frente a 173° en 2D']])
pie(s, '* MoveNet: valores medidos con GPU (memoria, Tabla 2). AP: precisión media en COCO según las publicaciones originales (Tabla 1).', y=7.6)
limpiar(s)

# ------------------------------------------------------------------ D5 · Ciclos
s = nueva('Texto', 'Contar ciclos en dos vistas', 'Cada vista usa la señal de brazada que puede ver',
          notas='La vista se decide sola: por tramos de 60 segundos miro si el tronco aparece horizontal o vertical. En '
          'lateral cuento brazadas con la mano más profunda respecto al cuerpo, porque YOLO copia el brazo visible en el '
          'oculto: cada pico es una brazada y en crol dos brazadas son un ciclo. De frente esa profundidad no se ve y uso '
          'el recorrido de cada muñeca en la dirección en que más se mueve, que saco con PCA. Lo validé con mi conteo '
          'manual: error entre el 6,5 y el 8,2 %, en lateral y en frontal. [≈ 1 min 15 s]')
imagen(s, FIG + 'aaron_brazadas.png', 0.99, 2.95, 8.4, 3.2)
texto(s, 0.99, 6.3, 8.4, 1.3, [[('Lateral: ', {'b': True, 'tam': 13}), ('profundidad de la mano más profunda (YOLO copia el brazo oculto); cada pico, una brazada.', {'tam': 13})],
                               [('Frontal: ', {'b': True, 'tam': 13}), ('recorrido de la muñeca en su dirección principal (PCA), en anchos de hombros.', {'tam': 13})]])
tabla(s, 9.8, 3.0, 5.2, [['Secuencia (P1, crol)', 'Manual', 'Sistema', 'Error'],
                         ['GX011614 · lateral', '54,0', '50,5', '−6,5 %'],
                         ['IMG_7207 · frontal', '80,0', '73,9', '−7,6 %'],
                         ['IMG_7215 · frontal', '51,1', '55,2', '+8,2 %']], [2.1, 0.95, 1.1, 1.05], tam=11, alto_fila=0.5)
texto(s, 9.8, 5.1, 5.2, 0.4, 'Frecuencia (ciclos/min) frente al conteo manual', tam=11, color=GRIS)
caja(s, 9.8, 5.65, 5.2, 1.75, NEGRO)
texto(s, 10.05, 5.65, 4.7, 1.75, [[('Vista automática: ', {'b': True, 'color': ROJO, 'tam': 13}),
      ('tramo frontal si ≥ 65 % de fotogramas con el tronco a > 55° de la horizontal.', {'color': BLANCO, 'tam': 13})]], ancla=MSO_ANCHOR.MIDDLE)
limpiar(s)

# ------------------------------------------------------------------ D6 · Fatiga
s = nueva('Texto', 'Fatiga con Isolation Forest', 'Sin etiquetas: cuánto se aparta cada ciclo del nadador fresco',
          notas='El plan inicial era una red recurrente supervisada, pero hacen falta ciclos etiquetados como fatigados y no '
          'los hay. Por eso uso Isolation Forest, que se entrena solo con la fase fresca del propio nadador, el primer 30 % '
          'de sus ciclos. Su idea: lo raro se aísla con pocos cortes aleatorios. Además tiene coste lineal y admite SHAP '
          'exacto. El inicio es el primer momento con tres ciclos seguidos por encima del percentil 95 de la fase fresca. '
          'Ese percentil lo elegí con un análisis de sensibilidad: con el 90 hay un 30 % de falsas alarmas y con el 99 se '
          'pierden fatigas. PELT, un detector de cambios independiente, sirve de contraste. [≈ 1 min 30 s]')
caja(s, 0.99, 3.0, 6.0, 1.05, GRIS_CL)
texto(s, 1.25, 3.0, 5.5, 1.05, [[('Descartada: red recurrente supervisada. ', {'b': True, 'tam': 13, 'color': GRIS}),
      ('Necesita ciclos etiquetados como fatigados: no existen.', {'tam': 13})]], ancla=MSO_ANCHOR.MIDDLE)
pasos = [('1', 'Fase fresca', 'Primer 30 % de los ciclos (mín. 5); variables estandarizadas con ella'),
         ('2', 'Isolation Forest', '500 árboles; lo anómalo se aísla con menos cortes aleatorios'),
         ('3', 'Inicio', '3 ciclos seguidos sobre el percentil 95 fresco; PELT de contraste'),
         ('4', 'TreeSHAP', 'Qué variable acerca cada ciclo a la fatiga')]
for i, (n, c, d) in enumerate(pasos):
    y = 4.25 + i * 0.83
    caja(s, 0.99, y, 0.65, 0.65, ROJO)
    texto(s, 0.99, y, 0.65, 0.65, n, tam=20, color=BLANCO, negrita=True, alin=PP_ALIGN.CENTER, ancla=MSO_ANCHOR.MIDDLE)
    texto(s, 1.8, y - 0.02, 5.2, 0.35, c, tam=14, negrita=True)
    texto(s, 1.8, y + 0.33, 5.2, 0.45, d, tam=12, color=GRIS)
imagen(s, FIG + 'sintetico_fatiga_timeline.png', 7.3, 2.95, 7.7, 3.6)
tabla(s, 7.3, 6.6, 7.7, [['Percentil', 'Detección', 'Falsas alarmas', 'Inicio (59-81 s)'],
                         ['90 · 95 · 99', '100 · 100 · 60 %', '30 · 10 · 0 %', '64,1 · 70,5 · 80,5 s']], [1.6, 2.0, 1.9, 2.2], tam=11, alto_fila=0.4)
pie(s, 'Gráfica y sensibilidad: datos sintéticos con fatiga programada (referencia conocida), no un nadador real.', y=7.55)
limpiar(s)

# ------------------------------------------------------------------ D9 · Resultados
s = nueva('Texto', 'Resultados', 'Nadadores reales y datos sintéticos, por separado',
          notas='Con nadadores reales: 17 secuencias de 4 participantes y 4 estilos, 95 ciclos válidos, la frecuencia con un '
          'error del 6,5 al 8,2 % frente al conteo manual y la familia del estilo bien en 12 de 13. En las sesiones reales '
          'no hubo fatiga ni falsas alarmas: son pasadas cortas con descansos. La gran limitación es la detección: el '
          'nadador fue analizable el 34 % del tiempo. Como no tengo una referencia real de fatiga, la compruebo con datos '
          'sintéticos donde sé la verdad: detecta el 100 % con un 10 % de falsas alarmas, y en tiempo real 10 de 10. '
          '[≈ 1 min 15 s]')
for fila, (et, col, items) in enumerate([
        ('Nadadores reales · 17 secuencias, 4 participantes, 4 estilos', ROJO,
         [('95', 'ciclos válidos (2,2 de 6,6 min analizables)'), ('6,5-8,2 %', 'error de frecuencia frente al conteo manual'),
          ('12/13', 'familia del estilo correcta (reglas)'), ('0', 'falsas alarmas en 3 sesiones de pasadas cortas')]),
        ('Datos sintéticos · referencia conocida', NEGRO,
         [('4,7 %', 'error mediano en la frecuencia de ciclo'), ('100 %', 'fatigas detectadas'),
          ('10 %', 'falsas alarmas'), ('10/10', 'detectadas en tiempo real, sin falsas alarmas')])]):
    y = 2.95 + fila * 2.35
    texto(s, 0.99, y, 14.0, 0.4, et, tam=15, color=col, negrita=True)
    for i, (n, e) in enumerate(items):
        x = 0.99 + i * 3.55
        caja(s, x, y + 0.45, 3.35, 1.75, GRIS_CL)
        cifra(s, x + 0.25, y + 0.55, 3.0, n, e, cnum=col, tam=32)
pie(s, 'Limitación principal: el nadador fue analizable el 34 % del tiempo grabado (detección bajo el agua).', y=7.7)
limpiar(s)

# ------------------------------------------------------------------ D11 · Conclusiones
s = nueva('Texto', 'Conclusiones y trabajo futuro', '7 objetivos cumplidos y 2 parciales',
          notas='Siete objetivos cumplidos y dos parciales: la fatiga está validada con datos sintéticos, pero falta la '
          'validación fisiológica con nadadores reales; y el estilo supervisado no generalizaba, por eso pasé a reglas. '
          'La lección principal: la calidad de los datos pesa más que el modelo. Una versión anterior daba un 99,99 % y '
          'era fuga de datos; desde entonces contrasté cada resultado con una referencia. El trabajo futuro sale de las '
          'limitaciones: series largas con referencia fisiológica, anotar fotogramas propios para medir la pose y '
          'ajustar el modelo a nadadores. Gracias. [≈ 1 min 15 s]')
obj = [('OE1', 'Modelo de pose', 'C'), ('OE2', 'Elevación a 3D', 'C*'), ('OE3', 'Ciclos de brazada', 'C'),
       ('OE4', 'Variables por ciclo', 'C'), ('OE5', 'Inicio de la fatiga', 'P'), ('OE6', 'Atribución SHAP', 'C'),
       ('OE7', 'Estilo de nado', 'P'), ('OE8', 'Vídeo y tiempo real', 'C'), ('OE9', 'Datos sintéticos', 'C')]
for i, (c, d, g) in enumerate(obj):
    x = 0.99 + (i % 3) * 2.75
    y = 3.0 + (i // 3) * 1.15
    caja(s, x, y, 2.6, 1.0, ROJO if g.startswith('C') else NEGRO)
    texto(s, x + 0.15, y + 0.1, 2.35, 0.35, f'{c} · {"Cumplido" if g == "C" else ("Cumplido*" if g == "C*" else "Parcial")}', tam=11, color=BLANCO, negrita=True)
    texto(s, x + 0.15, y + 0.48, 2.35, 0.45, d, tam=12, color=BLANCO)
texto(s, 0.99, 6.55, 8.1, 0.9, [[('La calidad de los datos pesa más que el modelo: ', {'b': True, 'color': ROJO, 'tam': 14}),
      ('cada resultado se contrastó con una referencia.', {'tam': 14})]])
caja(s, 9.5, 3.0, 5.5, 4.4, GRIS_CL)
texto(s, 9.8, 3.2, 5.0, 0.4, 'Limitaciones → trabajo futuro', tam=16, color=ROJO, negrita=True)
texto(s, 9.8, 3.75, 5.0, 3.6, [[('•  ' + t, {'tam': 12, 'esp': 6})] for t in [
    'Sin referencia fisiológica de la fatiga → series largas con lactato, esfuerzo percibido y valoración experta',
    'Detección parcial (34 %) → anotar fotogramas propios (OKS, PCK, mAP) y ajustar la pose con SwimXYZ',
    '3D poco fiable en piernas → adaptar MotionBERT a nadadores; ViTPose con GPU',
    'Umbrales fijados con los mismos vídeos → validar con nadadores nuevos']])
pie(s, '* Cumplido con limitaciones (3D válido en codo y cadera, no en rodilla).', y=7.6)
limpiar(s)

# ------------------------------------------------------------------ 16 · Contraportada
s = p.slides.add_slide(lay['Contraportada'])
s.shapes.title.text = 'Gracias'
ph(s, 16).text = '¿Preguntas?'
ph(s, 15).text = 'Diana Cruz'
ph(s, 22).text = 'StrokeLab · TFM Máster en IA'
ph(s, 23).text = 'Universidad Europea'
s.notes_slide.notes_text_frame.text = 'Muchas gracias. Quedo a disposición del tribunal para sus preguntas.'

# ================================================================== ANEXOS
s = p.slides.add_slide(lay['Blanco 01 rojo'])
s.shapes.title.text = 'Anexos'
ph(s, 18).text = 'Material de apoyo para las preguntas del tribunal'
limpiar(s)

s = nueva('Texto', 'A1 · Modelos de pose en CPU', 'Secuencia GX011614 (5120 × 2880 px), portátil de 4 hilos',
          notas='Si preguntan por qué YOLOv8n: es el más ligero sin perder detección, y en el vídeo real dio muchos más '
          'ciclos válidos que MoveNet. ViTPose se descartó por coste en CPU.')
tabla(s, 0.99, 3.15, 14.0, [['Modelo', 'Parámetros (M)', 'FPS en CPU', 'Detección (%)', 'Confianza'],
                            ['YOLOv8n-Pose (elegido)', '3,3', '6,6', '35,6', '0,76'],
                            ['YOLO11n-Pose', '2,9', '6,2', '37,6', '0,78'],
                            ['YOLOv8s-Pose', '11,6', '3,3', '35,6', '0,74'],
                            ['MoveNet Lightning', '—', 'No medido', '35-48 (GPU)', '0,34-0,37 (GPU)']],
      [4.6, 2.3, 2.3, 2.4, 2.4], tam=14, alto_fila=0.6, resaltar=(1,))
pie(s, 'La detección ronda el 36 % porque el nadador solo está en el encuadre parte del vídeo. En el mismo vídeo: 15 ciclos válidos con YOLO frente a 3 con MoveNet.', y=6.6)
limpiar(s)

POST.append(len(p.slides._sldIdLst))
s = nueva('Texto', 'B1 · Tamaño del modelo y sintéticos', 'Media de 4 pliegues por grabación · sin giro salvo indicación',
          notas='Tras el ajuste los tres tamaños quedan igual o el pequeño mejor: con unas 200 imágenes de entrenamiento '
          'el límite son los datos. Los sintéticos de SwimXYZ (vista frontal, fuera del agua) no mejoran la prueba, que '
          'es lateral bajo el agua, y aumentan las falsas detecciones.')
tabla(s, 0.99, 3.15, 14.0, [['Modelo', 'Detección', 'OKS', 'PCK@0,1', 'PCK@0,2', 'Falsos positivos (de 13)'],
                            ['YOLOv8n original (con giro, el del TFM)', '47 %', '0,10', '9 %', '15 %', '6'],
                            ['YOLOv8n ajustado', '78 %', '0,40', '37 %', '56 %', '3'],
                            ['YOLOv8s ajustado', '76 %', '0,37', '34 %', '54 %', '3,5'],
                            ['YOLOv8m ajustado', '69 %', '0,35', '33 %', '50 %', '2,5'],
                            ['YOLOv8n ajustado + 777 sintéticas (SwimXYZ)', '76 %', '0,39', '38 %', '54 %', '6,75']],
      [5.4, 1.6, 1.4, 1.6, 1.6, 2.4], tam=13, alto_fila=0.58, resaltar=(2,))
pie(s, 'Imágenes de Roboflow «Deep Dive Pose Technique» (CC BY 4.0), repartidas por grabación para evitar fuga de datos. Posterior a la entrega.', y=7.0)
limpiar(s)

POST.append(len(p.slides._sldIdLst))
s = nueva('Texto', 'B2 · Modelo ajustado en vídeos propios', '17 secuencias del TFM, misma resolución (640 px)',
          notas='Con el modelo ajustado el sistema analiza más tiempo y saca más ciclos, pero la frecuencia frente al '
          'conteo manual no mejora: la señal de la mano tiene picos dobles. Las reglas posteriores están calibradas con '
          'el modelo original; recalibrarlas exige más conteos manuales. Por eso el sistema del TFM mantiene el original.')
tabla(s, 0.99, 3.15, 7.0, [['', 'Original', 'Ajustado'], ['Tiempo analizable', '132 s', '166 s'], ['Ciclos válidos', '95', '109']],
      [2.8, 2.1, 2.1], tam=14, alto_fila=0.6)
tabla(s, 8.4, 3.15, 6.6, [['Frecuencia vs. manual', 'Original', 'Ajustado'], ['GX011614 (54,0)', '−6,5 %', '+35 %'],
                          ['IMG_7207 (80,0)', '−7,6 %', '−24 %'], ['IMG_7215 (51,1)', '+8,2 %', '+7 %']],
      [2.8, 1.9, 1.9], tam=14, alto_fila=0.6)
texto(s, 0.99, 5.9, 14.0, 1.4, 'Conclusión: un mejor modelo de pose no basta; hay que recalibrar el conteo de brazadas, la vista y el estilo con su nueva señal.',
      tam=16, negrita=True)
limpiar(s)

POST.append(len(p.slides._sldIdLst))
s = nueva('Texto', 'B3 · Vídeos públicos de televisión', 'Robustez fuera de las condiciones de diseño',
          notas='Probé dos vídeos de televisión. En la retransmisión del 800 libre de 2001, desde fuera del agua, con '
          'varios nadadores y cambios de plano, el sistema falla: la frecuencia salta de 40 a 90 ciclos por minuto. En '
          'un vídeo con cámara en el fondo y un solo nadador, detecta sola la vista frontal y sigue al nadador. El '
          'sistema está pensado para grabaciones de entrenamiento con un nadador.')
tarjeta(s, 0.99, 3.1, 6.8, 3.3, 'Retransmisión de carrera (fuera del agua)',
        'Varios nadadores y cambios de plano: el esqueleto salta de uno a otro y la frecuencia varía de 40 a 90 ciclos/min. No fiable.', num='✗')
tarjeta(s, 8.2, 3.1, 6.8, 3.3, 'Cámara en el fondo, un nadador',
        'Vista frontal detectada automáticamente y nadador seguido. 18 s: insuficiente para fatiga; frecuencia pendiente de conteo manual.',
        relleno=ROJO, ccab=BLANCO, ccue=BLANCO, num='✓')
limpiar(s)

s = nueva('Texto', 'A2 · Fatiga en las sesiones reales', 'Sesiones de pasadas cortas del mismo participante, estilo y cámara',
          notas='Ninguna sesión mostró fatiga ni falsas alarmas. Son pasadas cortas a ritmo técnico con descansos, no un '
          'esfuerzo continuo. No demuestra la capacidad de detectar fatiga real, pero sí que el sistema no inventa fatiga.')
tabla(s, 0.99, 3.15, 14.0, [['Sesión', 'Secuencias', 'Ciclos', 'Resultado'],
                            ['P1 · crol · GoPro', '3', '10', 'Sin fatiga sostenida'],
                            ['P1 · crol · móvil', '2', '7', 'Insuficiente (< 8 ciclos)'],
                            ['P4 · braza · GoPro', '2', '27', 'Sin fatiga sostenida'],
                            ['P4 · braza · móvil', '2', '4', 'Insuficiente (< 8 ciclos)'],
                            ['P3 · mariposa · GoPro', '2', '26', 'Sin fatiga sostenida']],
      [5.0, 2.4, 2.0, 4.6], tam=14, alto_fila=0.58)
limpiar(s)

s = nueva('Texto', 'A3 · Caso sintético completo (Tabla 7)', 'Secuencia de 120 s con fatiga programada entre t = 59 s y t = 81 s',
          notas='Si preguntan por la validación con referencia conocida: en vista lateral se estiman frecuencia, velocidad y '
          'distancia por ciclo con errores medianos del 4,7, 1,3 y 4,3 %; de frente, la frecuencia con un 0,3 %. El inicio '
          'se detecta a los 57,3 s, al comienzo de la transición, y SHAP señala variables alteradas en la simulación.')
tabla(s, 0.99, 3.1, 14.0, [['Medida', 'Vista lateral', 'Vista frontal'],
                           ['Ciclos analizados', '91', '98'],
                           ['Error mediano de la frecuencia de ciclo', '4,7 %', '0,3 %'],
                           ['Error mediano de la velocidad', '1,3 %', 'No observable de frente'],
                           ['Error mediano de la distancia por ciclo', '4,3 %', 'No observable de frente'],
                           ['Inicio de la fatiga detectado', 't = 57,3 s (ciclo 42)', 't = 57,8 s (ciclo 45)'],
                           ['Variables con mayor atribución SHAP', 'Apertura del hombro, asimetría de brazos, inclinación del tronco',
                            'Frecuencia de ciclo, asimetría de brazos, alcance del brazo']],
      [4.6, 4.7, 4.7], tam=13, alto_fila=0.58)
pie(s, 'Datos sintéticos. Fuente: memoria, Tabla 7.', y=7.4)
limpiar(s)

p.save('completa.pptx')
print('ok', len(p.slides), 'posteriores', POST)


def quedarse(entrada, salida, quitar):
    q = Presentation(entrada)
    ids = q.slides._sldIdLst
    for k, sid in reversed(list(enumerate(ids))):
        if k in quitar:
            q.part.drop_rel(sid.rId)
            ids.remove(sid)
    q.save(salida)


def titulo(sl):
    return sl.shapes.title.text if sl.shapes.title is not None else ''


def exportar(salida, titulos):
    """Guarda solo las diapositivas con esos títulos, en ese orden."""
    q = Presentation('completa.pptx')
    ids = q.slides._sldIdLst
    por_t = {titulo(sl): sid for sl, sid in zip(q.slides, list(ids))}
    falta = [t for t in titulos if t not in por_t]
    assert not falta, falta
    elegidos = [por_t[t] for t in titulos]
    for sid in list(ids):
        ids.remove(sid)
        if sid not in elegidos:
            q.part.drop_rel(sid.rId)
    for sid in elegidos:
        ids.append(sid)
    q.save(salida)


DEFENSA = ['StrokeLab', 'Problema y objetivo', 'Algoritmos: qué y por qué', 'Visión: pose bajo el agua',
           'Contar ciclos en dos vistas', 'Fatiga con Isolation Forest', 'SHAP explica la fatiga', 'Qué cambió y por qué',
           'Resultados', 'Demostración: 100 m libre', 'Conclusiones y trabajo futuro', 'Gracias']
APOYO = ['StrokeLab', 'Anexos', 'Pose 2D: por qué YOLOv8n', '3D con MotionBERT: cuándo sí y cuándo no',
         'Dos vistas, dos señales de brazada', '¿Por qué Isolation Forest?', 'Umbral e inicio: elegidos con datos',
         'TreeSHAP: cómo se explica cada ciclo', 'Estilo: del modelo supervisado a reglas', 'Validación con referencia conocida',
         'Del análisis al entrenador', 'A1 · Modelos de pose en CPU', 'A2 · Fatiga en las sesiones reales',
         'A3 · Caso sintético completo (Tabla 7)']
exportar('StrokeLab_defensa.pptx', DEFENSA)
exportar('StrokeLab_apoyo_preguntas.pptx', APOYO)
n = len(p.slides._sldIdLst)
quedarse('completa.pptx', 'StrokeLab_posterior_entrega.pptx', set(range(n)) - set(POST) - {0})
