"""Rellena la plantilla de memoria de la UEM con el contenido actual del TFM StrokeLab.

Uso:  python memoria/generar_memoria.py
Salida: memoria/TFM_StrokeLab_borrador.docx

El texto vive en este archivo: al tener resultados nuevos se cambia aquí y se vuelve a generar.
Marcado del texto: **negrita**, *cursiva*; lo que va entre [PENDIENTE ...] sale en rojo.
Al abrir el .docx, Word pregunta si actualiza los campos: responder «Sí» para rehacer índices y números de página.
"""
import copy
import re
from pathlib import Path

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from docx.table import Table
from docx.text.paragraph import Paragraph

AQUI = Path(__file__).resolve().parent
PLANTILLA = AQUI / 'Plantilla_memoria_TFM.docx'
SALIDA = AQUI / 'TFM_StrokeLab_borrador.docx'
FIG = AQUI / 'figuras'

TITULO = ('StrokeLab: análisis biomecánico explicable de la técnica y la fatiga en natación '
          'mediante visión por computador e inteligencia artificial')
TITULO_CORTO = 'StrokeLab: técnica y fatiga en natación con IA explicable'
AUTORA = 'Diana Cruz'
DIRECTOR = '______________________________'
NEGRO = RGBColor(0, 0, 0)
ROJO = RGBColor(0xC0, 0, 0)


# ---------------------------------------------------------------- utilidades de formato

def runs_con_formato(p, texto, size=None):
    """Añade runs a p interpretando **negrita**, *cursiva* y [PENDIENTE ...] (rojo)."""
    for trozo in re.split(r'(\*\*.+?\*\*|\*[^*]+?\*|\[PENDIENTE[^\]]*\]|`[^`]+`)', texto):
        if not trozo:
            continue
        if trozo.startswith('**'):
            r = p.add_run(trozo[2:-2]); r.bold = True
        elif trozo.startswith('[PENDIENTE'):
            r = p.add_run(trozo); r.font.color.rgb = ROJO; r.bold = True
        elif trozo.startswith('`'):
            r = p.add_run(trozo[1:-1]); r.font.name = 'Consolas'
        elif trozo.startswith('*') and len(trozo) > 2:
            r = p.add_run(trozo[1:-1]); r.italic = True
        else:
            r = p.add_run(trozo)
        if size:
            r.font.size = Pt(size)


def poner_texto(p, texto, size=None):
    """Sustituye el texto de un párrafo de la plantilla conservando el formato de su primer run, en negro."""
    runs = p.runs
    rpr = copy.deepcopy(runs[0]._r.rPr) if runs and runs[0]._r.rPr is not None else None
    for r in runs:
        r._r.getparent().remove(r._r)
    antes = len(p.runs)
    runs_con_formato(p, texto, size)
    for r in p.runs[antes:]:
        if rpr is not None:
            nuevo = copy.deepcopy(rpr)
            for tag in ('w:color', 'w:b', 'w:i'):
                for e in nuevo.findall(qn(tag)):
                    if tag == 'w:color' or r.bold or r.italic:
                        nuevo.remove(e)
            viejo = r._r.rPr
            if viejo is not None:                        # negrita/cursiva/rojo del marcado prevalecen
                for e in viejo:
                    nuevo.append(e)
                r._r.remove(viejo)
            r._r.insert(0, nuevo)
        if r.font.color.rgb is None:
            r.font.color.rgb = NEGRO


class Escritor:
    """Inserta bloques de contenido uno detrás de otro a partir de un elemento de la plantilla."""

    def __init__(self, doc, ancla, ppr_vineta, ppr_h2):
        self.doc, self.ultimo = doc, ancla
        self.ppr_vineta, self.ppr_h2 = ppr_vineta, ppr_h2

    def _poner(self, elem):
        self.ultimo.addnext(elem)
        self.ultimo = elem
        return elem

    def p(self, texto='', estilo='Normal', alinear=None, size=None):
        el = self._poner(OxmlElement('w:p'))
        par = Paragraph(el, self.doc._body)
        par.style = self.doc.styles[estilo]
        if alinear == 'centro':
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif alinear is None and estilo == 'Normal':
            par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        runs_con_formato(par, texto, size)
        return par

    def vinetas(self, items):
        for t in items:
            par = self.p(t, alinear='izq')
            par._p.insert(0, copy.deepcopy(self.ppr_vineta))

    def h2(self, texto):
        self.p(texto, estilo='Heading 2', alinear='izq')

    def h3(self, texto):
        self.p(texto, estilo='Heading 3', alinear='izq')

    def ecuacion(self, texto):
        self.p(texto, alinear='centro').runs[0].italic = True

    def leyenda(self, tipo, texto):
        """Leyenda con número automático (campo SEQ), para los índices de figuras y tablas."""
        par = self.p('', estilo='Caption', alinear='centro')
        par.add_run(f'{tipo} ')
        campo(par, f'SEQ {tipo} \\* ARABIC', '1')
        par.add_run('. ')
        runs_con_formato(par, texto)

    def figura(self, ruta, texto, ancho_cm=15):
        par = self.p('', alinear='centro')
        par.paragraph_format.keep_with_next = True
        par.add_run().add_picture(str(ruta), width=Cm(ancho_cm))
        self.leyenda('Figura', texto)

    def tabla(self, filas, texto, anchos=None, size=9):
        """filas[0] = cabecera. La leyenda va encima, como es habitual en tablas."""
        self.leyenda('Tabla', texto)
        t = self.doc.add_table(rows=len(filas), cols=len(filas[0]))
        t.style = self.doc.styles['Table Grid']
        for i, fila in enumerate(filas):
            for j, txt in enumerate(fila):
                celda = t.cell(i, j)
                par = celda.paragraphs[0]
                par.paragraph_format.space_before = Pt(1)
                par.paragraph_format.space_after = Pt(1)
                runs_con_formato(par, str(txt), size)
                if i == 0:
                    for r in par.runs:
                        r.bold = True
                    sombra = OxmlElement('w:shd')
                    sombra.set(qn('w:val'), 'clear'); sombra.set(qn('w:color'), 'auto'); sombra.set(qn('w:fill'), 'D9E2F3')
                    celda._tc.get_or_add_tcPr().append(sombra)
                if anchos:
                    celda.width = Cm(anchos[j])
        self._poner(t._tbl)
        self.p('', size=4)


def campo(par, instr, texto_previo=''):
    """Inserta un campo de Word (SEQ, TOC...) en el párrafo."""
    def fc(tipo):
        r = OxmlElement('w:r'); f = OxmlElement('w:fldChar'); f.set(qn('w:fldCharType'), tipo); r.append(f); return r
    par._p.append(fc('begin'))
    r = OxmlElement('w:r'); it = OxmlElement('w:instrText'); it.set(qn('xml:space'), 'preserve'); it.text = f' {instr} '
    r.append(it); par._p.append(r)
    par._p.append(fc('separate'))
    r = OxmlElement('w:r'); t = OxmlElement('w:t'); t.text = texto_previo; r.append(t); par._p.append(r)
    par._p.append(fc('end'))


def borrar(elem):
    elem.getparent().remove(elem)


# ---------------------------------------------------------------- contenido

RESUMEN = (
    'StrokeLab es un sistema que, a partir de un vídeo convencional de nado, responde a tres preguntas del '
    'entrenador: qué tan eficiente es la brazada, en qué momento aparece la fatiga técnica y por qué. Se organiza '
    'en dos verticales de inteligencia artificial. La vertical de visión estima la pose 2D del nadador con '
    'YOLOv8n-Pose en la CPU de un portátil, elegido tras una comparativa con otros modelos, y la eleva a 3D con '
    'MotionBERT. La vertical tabular cuenta las brazadas, con una señal propia para la vista lateral y otra para la '
    'frontal, calcula por ciclo medidas de codos, hombros, caderas, rodillas y pies, y modela con Isolation Forest '
    'el estado fresco del propio nadador. La desviación sostenida respecto a ese estado marca el inicio de la '
    'fatiga y SHAP la explica variable a variable. El modelo hidrodinámico se presenta como conocimiento previo, no '
    'como IA. Con un nadador sintético, el sistema localiza la fatiga introducida y SHAP señala las variables '
    'alteradas. Con vídeo real de un nadador de crol, la frecuencia de ciclo se aleja entre un 6,5 % y un 8,2 % de '
    'la cuenta manual en tres clips, en vista lateral y frontal. En los cinco clips disponibles de ese nadador no se '
    'detecta fatiga, un resultado coherente con pasadas cortas; localizarla en vídeo real exige grabar nado continuo.')
PALABRAS_CLAVE = ('natación, estimación de pose, detección de fatiga, Isolation Forest, SHAP, '
                  'inteligencia artificial explicable')
ABSTRACT = (
    'StrokeLab is a system that, from an ordinary swimming video, answers three coaching questions: how '
    'efficient the stroke is, when technical fatigue begins, and why. It is organised in two artificial '
    'intelligence verticals. The vision vertical estimates the swimmer’s 2D pose with YOLOv8n-Pose on a laptop CPU, '
    'chosen after comparing several models, and lifts it to 3D with MotionBERT. The tabular vertical counts strokes, '
    'with one signal for side views and another for front views, computes per-cycle elbow, shoulder, hip, knee and '
    'foot measures, and models the swimmer’s own fresh state with an Isolation Forest. A sustained deviation from '
    'that state marks the onset of fatigue, and SHAP explains it feature by feature. The hydrodynamic model is '
    'presented as domain knowledge, not as AI. On a synthetic swimmer the system locates the injected fatigue and '
    'SHAP points to the altered variables. On real video of a front-crawl swimmer, the stroke rate is within 6.5 % to '
    '8.2 % of a manual count in three clips, in side and front views. No fatigue is detected in the five available '
    'clips of that swimmer, which is consistent with short passes; locating it in real video requires continuous swimming.')
KEYWORDS = 'swimming, pose estimation, fatigue detection, Isolation Forest, SHAP, explainable artificial intelligence'

REFERENCIAS = [
    'Alberty, M., Sidney, M., Huot-Marchand, F., Hespel, J. M. y Pelayo, P. (2005). Intracyclic velocity variations and arm coordination during exhaustive exercise in front crawl stroke. *International Journal of Sports Medicine*, 26(6), 471-475.',
    'Bazarevsky, V., Grishchenko, I., Raveendran, K., Zhu, T., Zhang, F. y Grundmann, M. (2020). BlazePose: On-device real-time body pose tracking. *arXiv:2006.10204*.',
    'Chen, T. y Guestrin, C. (2016). XGBoost: A scalable tree boosting system. *Proceedings of KDD 2016*, 785-794.',
    'Chollet, D., Chalies, S. y Chatard, J. C. (2000). A new index of coordination for the crawl: description and usefulness. *International Journal of Sports Medicine*, 21(1), 54-59.',
    'Costill, D. L., Kovaleski, J., Porter, D., Kirwan, J., Fielding, R. y King, D. (1985). Energy expenditure during front crawl swimming: predicting success in middle-distance events. *International Journal of Sports Medicine*, 6(5), 266-270.',
    'Craig, A. B. y Pendergast, D. R. (1979). Relationships of stroke rate, distance per stroke, and velocity in competitive swimming. *Medicine and Science in Sports*, 11(3), 278-283.',
    'Einfalt, M., Zecha, D. y Lienhart, R. (2018). Activity-conditioned continuous human pose estimation for performance analysis of athletes using the example of swimming. *IEEE WACV 2018*.',
    'Fiche, G., Sevestre, V., Gonzalez-Barral, C., Leglaive, S. y Séguier, R. (2023). SwimXYZ: A large-scale dataset of synthetic swimming motions and videos. *ACM SIGGRAPH Conference on Motion, Interaction and Games (MIG)*.',
    'Google (2021). MoveNet: Ultra fast and accurate pose detection model. *TensorFlow Hub*.',
    'Jocher, G., Chaurasia, A. y Qiu, J. (2023). *Ultralytics YOLOv8*. GitHub.',
    'Killick, R., Fearnhead, P. y Eckley, I. A. (2012). Optimal detection of changepoints with a linear computational cost. *Journal of the American Statistical Association*, 107(500), 1590-1598.',
    'Lin, T.-Y. et al. (2014). Microsoft COCO: Common objects in context. *ECCV 2014*.',
    'Liu, F. T., Ting, K. M. y Zhou, Z.-H. (2008). Isolation Forest. *IEEE ICDM 2008*, 413-422.',
    'Lundberg, S. M. y Lee, S.-I. (2017). A unified approach to interpreting model predictions. *NeurIPS 2017*.',
    'Lundberg, S. M. et al. (2020). From local explanations to global understanding with explainable AI for trees. *Nature Machine Intelligence*, 2, 56-67.',
    'Maji, D., Nagori, S., Mathew, M. y Poddar, D. (2022). YOLO-Pose: Enhancing YOLO for multi person pose estimation using object keypoint similarity loss. *CVPR Workshops 2022*.',
    'Savitzky, A. y Golay, M. J. E. (1964). Smoothing and differentiation of data by simplified least squares procedures. *Analytical Chemistry*, 36(8), 1627-1639.',
    'Toussaint, H. M. y Beek, P. J. (1992). Biomechanics of competitive front crawl swimming. *Sports Medicine*, 13(1), 8-24.',
    'Xu, Y., Zhang, J., Zhang, Q. y Tao, D. (2022). ViTPose: Simple vision transformer baselines for human pose estimation. *NeurIPS 2022*.',
    'Zhu, W., Ma, X., Liu, Z., Liu, L., Wu, W. y Wang, Y. (2023). MotionBERT: A unified perspective on learning human motion representations. *ICCV 2023*.',
]


def cap1_contexto(w):
    w.p('En natación, la velocidad depende de mantener una técnica eficiente durante toda la prueba. Con la fatiga, '
        'el nadador suele aumentar la frecuencia de brazada, acorta la distancia por ciclo y su técnica se degrada '
        '(Craig y Pendergast, 1979; Alberty et al., 2005). El entrenador percibe estos cambios a simple vista, de forma '
        'subjetiva y sin poder precisar cuándo empiezan ni qué aspecto cambia primero.')
    w.p('La física del agua explica por qué importa la eficiencia: la resistencia al avance crece con el cuadrado de la '
        'velocidad y la potencia necesaria, con el cubo. Cuando la fatiga reduce la potencia disponible, el nadador '
        'solo puede sostener la velocidad con una técnica más eficiente. Este modelo hidrodinámico se usa en el trabajo '
        'como conocimiento previo del dominio (Capítulo 2), no como parte de la inteligencia artificial.')


def cap1_problema(w):
    w.p('No existe una herramienta accesible que, a partir de un único vídeo y sin sensores ni marcadores, responda '
        'al entrenador **qué tan eficiente es la brazada, en qué momento aparece la fatiga y por qué**, es decir, qué '
        'variables técnicas han cambiado. Los sistemas comerciales requieren equipamiento específico y entregan '
        'métricas sin explicar su relación con el rendimiento.')
    w.p('El proyecto se plantea como un trabajo de investigación aplicada con un producto funcional, sin colaboración '
        'con empresa. Los datos son vídeos subacuáticos de ocho nadadores de un club, grabados con cámara GoPro.')


def cap1_objetivos(w):
    w.p('El objetivo general es desarrollar un sistema de IA explicable que, a partir de vídeo, cuantifique la '
        'eficiencia de la brazada, localice el inicio de la fatiga y explique sus causas mediante SHAP, y que funcione '
        'en un ordenador personal sin GPU. Los objetivos específicos (Capítulo 3) cubren la selección del modelo de '
        'pose, el conteo de brazadas, la detección no supervisada de la fatiga, su explicación y la clasificación del estilo.')


def cap1_resultados(w):
    w.vinetas([
        'Sistema completo ejecutable en la CPU de un portátil, para un vídeo (`analizar.py`) o una carpeta entera (`lote.py`), con pruebas automáticas.',
        'Comparativa de modelos de pose en CPU sobre vídeo real: YOLOv8n-Pose es el más equilibrado (6,6 FPS, confianza 0,76).',
        'Conteo de brazadas en vista lateral y frontal, validado con la cuenta manual en tres clips reales: error del 6,5 %, 7,6 % y 8,2 %.',
        'Detección de la fatiga y explicación SHAP validadas con un nadador sintético, de lado y de frente.',
        'Análisis completo de un nadador real (Aaron, crol, 5 clips): medidas por ciclo y ausencia de fatiga en pasadas cortas.',
        'Validación del 3D (MotionBERT) frente al 2D: fiable en codo y cadera, no en la rodilla de un nadador horizontal.',
        'Vídeo anotado para el entrenador centrado en el estado de fatiga.',
        'Fatiga en vídeo real: no aparece en los clips disponibles (pasadas cortas); su localización requiere grabar nado continuo.',
    ])


def cap1_estructura(w):
    w.p('El Capítulo 2 revisa el estado del arte y el modelo hidrodinámico. El Capítulo 3 detalla los objetivos. El '
        'Capítulo 4 describe la planificación, la solución (vertical de visión y vertical tabular), los recursos, el '
        'presupuesto y los resultados. El Capítulo 5 discute las decisiones y limitaciones, el Capítulo 6 recoge las '
        'conclusiones y el Capítulo 7 las líneas futuras. Los anexos incluyen la guía de ejecución y la estructura del código.')


def cap2_estado(w):
    w.p('Esta sección revisa los cuatro campos en los que se apoya el sistema: la biomecánica del crol, la fatiga en '
        'natación, la estimación de pose humana y la detección de anomalías con explicación SHAP.')
    w.h3('Biomecánica del crol y eficiencia')
    w.p('La velocidad media de nado es el producto de la frecuencia de ciclo (SR) y la distancia por ciclo (DPS): '
        'v = SR · DPS (Craig y Pendergast, 1979). Los nadadores más eficientes alcanzan una velocidad dada con mayor DPS '
        'y menor SR. El Índice de Brazada (SI = v · DPS) se asocia a la economía del nado (Costill et al., 1985). También '
        'se relacionan con la eficiencia la flexión del codo en el agarre, el alcance de la brazada, la simetría entre '
        'brazos y la alineación del cuerpo (Toussaint y Beek, 1992; Chollet et al., 2000).')
    w.h3('Fatiga en natación')
    w.p('Con la fatiga se observa un descenso de la DPS, a menudo compensado con un aumento de la SR, junto con cambios '
        'en la coordinación de brazos (Alberty et al., 2005). Estos cambios son individuales: cada nadador se fatiga a su '
        'manera. Por eso tiene sentido comparar al nadador consigo mismo y no con una norma poblacional.')
    w.h3('Estimación de pose humana')
    w.p('Los modelos de estimación de pose localizan las articulaciones en la imagen. Este trabajo usa el formato COCO '
        'de 17 puntos (Lin et al., 2014). La Tabla 1 resume los modelos considerados.')
    w.tabla([
        ['Modelo', 'Tipo', 'Características relevantes'],
        ['YOLO-Pose / YOLOv8-Pose (Maji et al., 2022; Jocher et al., 2023)', 'Detección + puntos en una etapa', 'Multipersona; tamaños n, s, m; coordenadas en píxeles originales'],
        ['MoveNet Lightning (Google, 2021)', 'Una persona, entrada 192 × 192', 'Muy ligero; necesita recorte de seguimiento en vídeo de alta resolución'],
        ['BlazePose / MediaPipe (Bazarevsky et al., 2020)', 'Una persona, 33 puntos', 'Orientado a móvil; se convierte a COCO-17'],
        ['ViTPose (Xu et al., 2022)', 'Transformer, dos etapas', 'Mayor precisión en COCO; coste alto en CPU'],
        ['MotionBERT (Zhu et al., 2023)', 'Elevación 2D → 3D', 'Transformer temporal; entrenado con personas de pie (Human3.6M)'],
    ], 'Modelos de estimación de pose considerados.', anchos=[5.5, 4, 6.5])
    w.p('En natación, la estimación de pose es más difícil por la refracción, las burbujas, la oclusión y la escasez de '
        'datos etiquetados (Einfalt et al., 2018). El conjunto sintético SwimXYZ (Fiche et al., 2023) ofrece vídeos de '
        'los cuatro estilos para entrenar y evaluar.')
    w.h3('Detección de anomalías y explicabilidad')
    w.p('Isolation Forest (Liu et al., 2008) aísla observaciones con particiones aleatorias: las anómalas se aíslan en '
        'menos particiones. Puede entrenarse solo con datos «normales», algo adecuado cuando no hay etiquetas de fatiga. '
        'El algoritmo PELT (Killick et al., 2012) localiza puntos de cambio en una serie y se usa como contraste. SHAP '
        '(Lundberg y Lee, 2017) reparte la salida de un modelo entre sus variables con valores de Shapley; para modelos '
        'de árboles, TreeSHAP los calcula de forma exacta (Lundberg et al., 2020).')


def cap2_contexto(w):
    w.p('El director del trabajo indicó (1 de septiembre de 2026) que el modelo hidrodinámico debía figurar como '
        'conocimiento previo y no como IA. Es la física que justifica por qué importa la eficiencia técnica. La fuerza '
        'de arrastre que se opone al avance es:')
    w.ecuacion('F = ½ · ρ · C_D · A · v²')
    w.p('donde ρ es la densidad del agua (≈ 1000 kg/m³), C_D el coeficiente de arrastre, A el área frontal y v la '
        'velocidad. La potencia necesaria para vencerla crece con el cubo de la velocidad:')
    w.ecuacion('P = F · v = ½ · ρ · C_D · A · v³')
    w.p('Nadar un 10 % más rápido exige un 33 % más de potencia (1,1³ ≈ 1,33). Cuando la fatiga reduce la potencia '
        'disponible, el nadador solo mantiene la velocidad si mejora la eficiencia (Toussaint y Beek, 1992). C_D y A '
        'varían con cada nadador y no se pueden medir con fiabilidad desde un vídeo 2D, así que la potencia no se usa '
        'como variable de los modelos: se usan indicadores cinemáticos medibles, interpretados a la luz de esta relación.')
    w.p('La aportación del proyecto es combinar, en un sistema de bajo coste que funciona en un portátil, una detección '
        'no supervisada del momento de fatiga y una explicación por variable comprensible para el entrenador. Los '
        'trabajos revisados miden la técnica o detectan la fatiga, pero no ofrecen ambas cosas a la vez.')


def cap2_problema(w):
    w.p('El problema se concreta en tres preguntas: (1) cómo extraer la pose de un nadador bajo el agua con un modelo '
        'que funcione en CPU; (2) cómo convertir esa pose en ciclos de brazada y variables con significado biomecánico; '
        '(3) cómo decidir, sin etiquetas de fatiga, cuándo la técnica de un nadador se ha degradado y explicar por qué. '
        'La tercera pregunta es la central y se aborda con detección de anomalías respecto al estado fresco del propio '
        'nadador y explicación con SHAP.')


def cap3_generales(w):
    w.p('El objetivo general del presente trabajo es desarrollar un sistema de inteligencia artificial explicable '
        'que, a partir de un vídeo de nado y en un ordenador personal sin GPU, cuantifique la eficiencia de la '
        'brazada, localice el momento en que aparece la fatiga técnica y explique sus causas mediante SHAP.')


def cap3_especificos(w):
    w.vinetas([
        'OE1. Comparar empíricamente modelos de estimación de pose (YOLO en varios tamaños, MoveNet y MediaPipe) sobre vídeo subacuático real y en CPU, y seleccionar el más adecuado.',
        'OE2. Elevar la pose a 3D con MotionBERT para vistas frontales y oblicuas, y validar el 3D frente al 2D.',
        'OE3. Segmentar automáticamente el nado en ciclos de brazada y validarlo frente a una cuenta manual.',
        'OE4. Calcular por ciclo indicadores de eficiencia y medidas de codos, hombros, caderas, rodillas y pies.',
        'OE5. Detectar el inicio de la fatiga como desviación sostenida respecto a la técnica fresca del propio nadador.',
        'OE6. Explicar cada detección con SHAP y traducirla a un texto comprensible para el entrenador.',
        'OE7. Clasificar el estilo de nado con validación agrupada por vídeo.',
        'OE8. Generar un vídeo anotado que muestre al entrenador el estado de fatiga a lo largo del nado.',
    ])


def cap3_beneficios(w):
    w.p('El entrenador obtiene, con una cámara que ya tiene, una medida objetiva de cuándo y cómo se degrada la técnica '
        'de cada nadador, y qué aspecto conviene trabajar. Al ejecutarse en un portátil, el sistema no depende de '
        'servicios de pago ni de enviar los vídeos fuera del club. En el plano académico, el trabajo muestra cómo '
        'aplicar detección de anomalías explicable a un problema deportivo sin etiquetas.')


def cap4_planificacion(w):
    w.p('El proyecto se ha desarrollado en cinco fases. La Tabla 2 resume las fechas principales.')
    w.tabla([
        ['Fase', 'Periodo', 'Actividades'],
        ['1. Planteamiento', 'Mayo-julio de 2026', 'Anteproyecto, revisión bibliográfica, grabación de los vídeos de 8 nadadores'],
        ['2. Primer prototipo', 'Hasta agosto de 2026', 'Pipeline en Google Colab: MoveNet, MotionBERT, variables y clasificación'],
        ['3. Revisión del director', '1 de septiembre de 2026', 'Indicaciones: SHAP como eje, dos verticales, modos, modelo hidrodinámico, optimizar YOLO'],
        ['4. Rediseño y validación', 'Septiembre-octubre de 2026', 'Fatiga por ciclo con Isolation Forest y SHAP, comparativa en CPU, paso a ejecución local, vista frontal, análisis por lotes, validación con Aaron'],
        ['5. Resultados y memoria', 'Hasta el 15 de octubre de 2026', 'Análisis de vídeos largos, 8 nadadores, redacción y entrega'],
    ], 'Planificación del proyecto.', anchos=[3.5, 4, 8.5])


def cap4_solucion(w):
    w.p('StrokeLab se organiza en dos verticales de IA conectadas por un formato intermedio común: una secuencia de 17 '
        'puntos articulares por fotograma (Figura 1). La vertical de visión convierte el vídeo en puntos; la vertical '
        'tabular convierte los puntos en ciclos, variables, eficiencia y fatiga explicada con SHAP.')
    w.figura(FIG / 'arquitectura.png', 'Arquitectura de StrokeLab: dos verticales de IA.')
    w.p('El sistema admite tres modos de entrada. El modo **vídeo** recorre las dos verticales. El modo **tabular** recibe '
        'variables por ciclo ya calculadas (CSV) y entra directamente en la vertical tabular. El modo **audio** '
        '(sonido de brazadas y respiración) queda como trabajo futuro. Todo se ejecuta en local con un único programa:')
    w.p('python analizar.py "<vídeo>" --nadador "<nombre>"', alinear='centro', size=9)

    w.h3('Vertical de visión: selección del modelo de pose')
    w.p('Para optimizar el modelo de visión se midieron los candidatos sobre los mismos fotogramas, repartidos por todo '
        'el vídeo, con cuatro métricas: fotogramas por segundo en la CPU, tasa de detección, confianza media de los puntos '
        'y una puntuación combinada (detección × confianza). Al principio se eligió MoveNet por su fluidez en CPU. Al '
        'medir sobre los vídeos subacuáticos, YOLO detectó al nadador con el doble de confianza (0,73-0,77 frente a '
        '0,34-0,37) y produjo 15 ciclos válidos frente a 3. Como el vídeo anotado se genera después del análisis, la '
        'ventaja de fluidez de MoveNet dejó de ser relevante. Se eligió la variante más ligera que no pierde detección: '
        'YOLOv8n-Pose (Tabla 3). MoveNet y MediaPipe quedan como opciones (`--modelo`); ViTPose se descartó por su coste en CPU.')
    w.tabla([
        ['Modelo', 'Parámetros (M)', 'FPS en CPU', 'Detección (%)', 'Confianza', 'Puntuación'],
        ['**YOLOv8n-Pose (elegido)**', '3,3', '6,6', '35,6', '0,76', '0,27'],
        ['YOLO11n-Pose', '2,9', '6,2', '37,6', '0,78', '0,29'],
        ['YOLOv8s-Pose', '11,6', '3,3', '35,6', '0,74', '0,27'],
        ['MoveNet Lightning', '—', 'no medido en CPU', '35-48 (GPU)', '0,34-0,37 (GPU)', '—'],
        ['MediaPipe Pose', '—', 'no medido en CPU', '—', '—', '—'],
    ], 'Comparativa en la CPU del portátil (4 hilos) sobre GX011614 (Aaron, crol, 5120 × 2880). La detección '
       'ronda el 36 % porque el nadador solo está en cuadro parte del vídeo.', anchos=[4.5, 2.3, 2.2, 2.4, 2.2, 2.4])
    w.p('YOLOv8n-Pose procesa uno de cada dos fotogramas, reducidos a 1920 px de lado. Las coordenadas se devuelven en '
        'píxeles del vídeo original. La opción `--girar auto` prueba el fotograma sin girar y girado ±90°, porque YOLO se '
        'entrenó con personas de pie; en el vídeo de Aaron detectó mejor sin girar.')

    w.h3('Vertical de visión: limpieza y filtros anatómicos')
    w.vinetas([
        'Se descartan los puntos con confianza inferior a 0,30; se interpolan los huecos de hasta 0,4 s y se suaviza con un filtro Savitzky-Golay (Savitzky y Golay, 1964).',
        '**Plausibilidad anatómica.** Bajo el agua, el modelo a veces sitúa la cadera casi sobre el hombro. Se descartan los fotogramas con un tronco fuera de [0,5, 2] veces su mediana, los brazos y piernas de longitud imposible y los codos por debajo de 25°.',
        '**Tronco girado.** YOLO a veces dibuja un esqueleto vertical bajo la cabeza de un nadador horizontal. Se descartan los fotogramas cuyo tronco se desvía más de 45° de la dirección habitual del nadador. En el vídeo de Aaron eliminó el 11,5 % de los fotogramas y la inclinación media pasó de 42° a 9°.',
    ])

    w.h3('Vertical de visión: elevación a 3D con MotionBERT')
    w.p('La pose 2D se eleva a 3D con MotionBERT-Lite en CPU (unos 25 s por vídeo). Como el modelo se entrenó con '
        'personas de pie, cada fotograma se centra en la pelvis, se gira hasta dejar el tronco vertical y se normaliza '
        'por el tamaño del cuerpo; los ángulos articulares no cambian con ese giro. El 3D se mantiene porque hay vídeos '
        'frontales y de varios ángulos. Su validación se presenta en la Sección 4.6.')

    w.h3('Vertical tabular: ciclos de brazada')
    w.p('El análisis se hace por ciclo de brazada, no por fotograma: cada observación tiene sentido biomecánico y se '
        'evita la correlación entre fotogramas consecutivos. La señal para contar brazadas es la **profundidad de la '
        'mano más profunda** respecto al eje del cuerpo, en 2D y en longitudes de tronco (Figura 2). Esta elección '
        'surgió del vídeo real: en vista lateral, el modelo copia el brazo visible en el oculto, así que no se puede '
        'confiar en distinguir el brazo izquierdo del derecho. El ritmo típico es la mediana de los intervalos entre '
        'brazadas dentro del rango fisiológico (0,35-1,0 s en crol). Un ciclo son dos brazadas; si se pierde una, el intervalo '
        'doble se reconoce y se cuenta.')
    w.figura(FIG / 'aaron_brazadas.png', 'Señal de profundidad de la mano y brazadas detectadas en el vídeo de Aaron (GX011614).')
    w.p('**Vista frontal.** Cuando el nadador viene hacia la cámara o se le graba desde el borde, la profundidad de la '
        'mano respecto al cuerpo no se ve. En esa vista (`--vista frontal`) la señal es el recorrido de cada muñeca '
        'respecto al centro de los hombros, en la dirección en que más se mueve (componente principal, con cada brazo '
        'centrado) y dividido por el ancho de hombros, que de frente es más estable que el tronco. De frente sí se '
        'distinguen los dos brazos, así que la asimetría es más fiable que de lado. En esta vista no se calculan la '
        'inclinación del tronco ni la velocidad, y los ángulos se toman del 3D.')
    w.p('**Estilo.** El estilo fija cuántas brazadas forman un ciclo y el ritmo plausible (Tabla 4).')
    w.tabla([
        ['Estilo', 'Brazadas por ciclo', 'Tiempo entre brazadas'],
        ['Crol', '2 (brazos alternos)', '0,35-1,0 s'],
        ['Espalda', '2 (brazos alternos)', '0,35-1,2 s'],
        ['Mariposa', '1 (brazos a la vez)', '0,7-2,0 s'],
        ['Braza', '1 (brazos a la vez)', '0,7-2,4 s'],
    ], 'Definición del ciclo según el estilo. Validado con vídeo real solo en crol; el resto, con datos sintéticos.', anchos=[4, 5, 5])

    w.h3('Vertical tabular: variables por ciclo')
    w.tabla([
        ['Variable', 'Definición', 'Relación con eficiencia y fatiga'],
        ['Frecuencia de ciclo, SR (ciclos/min)', '60 / duración del ciclo', 'Aumenta como compensación con la fatiga'],
        ['DPS (m) y SI (m²/s)', 'v · duración; v · DPS (requieren calibración)', 'Principales indicadores de eficiencia'],
        ['Flexión del codo (°), izq. y dcho.', 'Percentil 10 del ángulo hombro-codo-muñeca', 'Eficacia de la fase subacuática'],
        ['Apertura del hombro (°)', 'Percentil 90 del ángulo codo-hombro-cadera', 'Extensión del brazo en la entrada'],
        ['Ángulo de cadera (°)', 'Ángulo medio hombro-cadera-rodilla', 'Alineación del cuerpo y arrastre'],
        ['Flexión de rodilla (°)', 'Percentil 10 del ángulo cadera-rodilla-tobillo', 'Calidad de la patada'],
        ['Alcance del brazo (troncos)', 'Recorrido de la muñeca sobre el eje del cuerpo', 'Longitud de la brazada'],
        ['Asimetría de brazos (%)', '100 · |alcance izq. − dcho.| / media', 'Descompensación lateral'],
        ['Inclinación del tronco (°)', 'Ángulo cadera-hombro respecto a la horizontal', 'Hundimiento de cadera, más arrastre'],
        ['Amplitud de patada y patadas por ciclo (pies)', 'Separación de tobillos y número de máximos', 'Contribución y ritmo de la patada'],
    ], 'Variables calculadas por ciclo de brazada.', anchos=[4.8, 5.4, 5.8])
    w.p('Los mínimos y máximos de cada ciclo se toman como percentiles 10 y 90: con el mínimo puro, un solo fotograma '
        'mal detectado fijaba el valor del ciclo (en GX011614 daba rodillas de 12°). Los ángulos y las distancias '
        'relativas al tronco no necesitan calibración. La velocidad, la DPS y el SI solo se calculan si la cámara es '
        'fija y se conoce la anchura en metros del encuadre (`--metros-encuadre`).')

    w.h3('Vertical tabular: detección del inicio de la fatiga')
    w.p('No hay etiquetas de fatiga, así que se plantea como detección de anomalías respecto al estado fresco del propio nadador:')
    w.vinetas([
        'Fase base: el primer 30 % de los ciclos (mínimo 5) se toma como técnica fresca; las variables se estandarizan con ella.',
        'Modelo: Isolation Forest de 500 árboles entrenado solo con la fase base; cada ciclo recibe una puntuación de anomalía.',
        'Umbral: percentil 95 de las puntuaciones de la fase base.',
        'Inicio de la fatiga: primer ciclo a partir del cual la media móvil de 3 ciclos supera el umbral durante 3 ciclos seguidos.',
        'Contraste: PELT (implementación propia, coste L2) sobre la serie de puntuaciones.',
        'Variables redundantes fuera del modelo: como v = SR · DPS y la potencia es ∝ v³, no se usan ni la velocidad, ni el SI, ni la potencia.',
    ])

    w.h3('Vertical tabular: explicación con SHAP')
    w.p('Sobre el Isolation Forest se calculan valores SHAP exactos con TreeSHAP, con el signo cambiado para que un '
        'valor positivo signifique «empuja hacia la fatiga». En cada ejecución se comprueba que la suma de los SHAP '
        'se correlaciona positivamente con la puntuación de anomalía. Se generan tres salidas: un gráfico global de qué '
        'variables explican la fatiga, un gráfico de cascada del ciclo de inicio y un texto para el entrenador con las '
        'cuatro variables que más contribuyen y su cambio respecto a la fase fresca.')

    w.h3('Análisis por sesión, por lotes y vídeo anotado')
    w.p('Cada clip de GoPro suele recoger una sola pasada (10-20 s de nado), demasiado poco para ver fatiga. `sesion.py` '
        'une los ciclos de varias pasadas de un mismo nadador en orden de grabación y aplica el mismo modelo; indica en '
        'qué pasada y en qué segundo del clip aparece la fatiga. `lote.py` analiza todos los vídeos de una carpeta a '
        'partir de una lista editable (nadador, estilo, vista y sesión), une las sesiones y se puede interrumpir y '
        'reanudar; cada resultado guarda la versión del análisis y se rehace si el código cambia. `informe_nadador.py` '
        'resume un nadador y un estilo: tiempo analizable y ciclos por clip y medidas por ciclo. El vídeo anotado '
        '(Figura 3) muestra el estado FRESCO o FATIGA, el ciclo, la frecuencia y una barra temporal con la anomalía de '
        'cada ciclo, el umbral y el inicio de la fatiga. Los ángulos quedan en las tablas (`--panel completo` los muestra '
        'en el vídeo).')
    w.p('El estilo se clasifica con un bosque aleatorio sobre rasgos por ventana de 4 s, con validación agrupada por '
        'vídeo (GroupKFold); el 99,99 % de precisión de una versión anterior se debía a fuga de datos entre fotogramas '
        'de un mismo vídeo. Sus resultados se presentan en la Sección 4.6.')
    w.figura(FIG / 'panel_video.png', 'Panel del vídeo anotado (nadador sintético, t = 70 s; la fatiga empieza en 51,9 s).', ancho_cm=13)
    w.p('Herramientas: Python 3, Ultralytics (YOLO), PyTorch (MotionBERT), OpenCV, NumPy, pandas, scikit-learn, shap, '
        'Matplotlib y Git. El código incluye pruebas automáticas que se ejecutan antes de cada cambio (Anexo C).')


def cap4_recursos(w):
    w.vinetas([
        'Portátil personal con Windows y CPU de 4 hilos, sin GPU.',
        'Cámara subacuática GoPro (vídeo 5K a 30 fps) y teléfono móvil (1080 × 1920, 60 fps).',
        'Vídeos de 8 nadadores de un club (crol, espalda, braza y mariposa), usados solo con fines académicos.',
        'Software libre: Python y librerías de código abierto; pesos preentrenados públicos de YOLOv8 y MotionBERT.',
        'Google Colab (gratuito) en la fase de prototipo; Google Drive para compartir vídeos y resultados.',
    ])


def cap4_presupuesto(w):
    w.p('El presupuesto valora el tiempo invertido y el equipo utilizado, aunque no haya sido necesario comprarlo. '
        'Todo el software es libre, por lo que su coste es 0 €.')


def cap4_viabilidad(w):
    w.p('El sistema es técnicamente viable en el equipo de un club: funciona en un portátil sin GPU y procesa un vídeo '
        '5K de 46 s en unos 9 minutos (288 s de pose, 25 s de 3D y unos 205 s del vídeo anotado), sin coste de licencias. '
        'La principal condición es la grabación: hace falta al menos un minuto de nado continuo, o varias pasadas de una '
        'misma sesión, para que la fatiga pueda aparecer. Los vídeos deben tratarse con el consentimiento de los nadadores.')


def cap4_resultados(w):
    w.h3('Validación del método con un nadador sintético')
    w.p('Antes del vídeo real, el método se validó con un nadador sintético de 90 s a 30 fps con una fatiga progresiva '
        'centrada en t = 55 s (más frecuencia, menos alcance, más flexión del codo, más inclinación y asimetría creciente). '
        'Se añadieron ruido, puntos de baja confianza, un hueco de detección, caderas sobre el hombro, esqueletos de pie y '
        'confusiones entre brazos. Resultados: 67 ciclos válidos; **inicio de la fatiga en el ciclo 35 (t = 51,9 s)**, '
        'dentro de la transición introducida; PELT sitúa el cambio en el ciclo 33 (t = 49,4 s); la correlación de '
        'comprobación del signo de SHAP es 0,999 (Figuras 4 a 6).')
    w.figura(FIG / 'sintetico_fatiga_timeline.png', 'Nadador sintético: anomalía por ciclo, umbral e inicio de la fatiga.')
    w.p('SHAP identifica como causas variables que se alteraron: alcance del brazo derecho (1,78 → 1,05 troncos), '
        'asimetría de brazos (2 % → 23 %) y amplitud de patada (0,31 → 0,21 troncos).')
    w.figura(FIG / 'sintetico_shap_summary.png', 'SHAP global: variables que explican la fatiga del nadador sintético.', ancho_cm=12)
    w.figura(FIG / 'sintetico_shap_waterfall_inicio.png', 'SHAP local: por qué el ciclo 35 ya es fatiga.', ancho_cm=12)
    w.p('Con un nadador sintético visto de frente (`tests/test_frontal.py`), la frecuencia estimada es 48,9 ciclos/min '
        '(valor real ≈ 50), el inicio de la fatiga se sitúa en t = 47,5 s y SHAP señala el alcance del brazo, la '
        'frecuencia y la asimetría, que son las variables alteradas.')

    w.h3('Caso de demostración con un nadador simulado')
    w.p('Para mostrar todas las capacidades con una verdad conocida se generó un **nadador ficticio** (no son datos '
        'reales; `caso_ficticio.py`): crol durante 120 s, con cámara fija que cubre los 25 m (velocidad calibrada) y '
        'fatiga programada que sube del 10 % al 90 % entre los segundos 59 y 81 (más frecuencia, menos velocidad y '
        'distancia por ciclo, menos alcance, más flexión del codo, cadera hundida y asimetría). Se analizó en vista '
        'lateral y frontal (Tabla 6).')
    w.tabla([
        ['Medida', 'Vista lateral', 'Vista frontal'],
        ['Ciclos analizados', '91', '98'],
        ['Error mediano de la frecuencia de ciclo', '4,7 %', '0,3 %'],
        ['Error mediano de la velocidad', '1,3 %', 'no medible de frente'],
        ['Error mediano de la distancia por ciclo', '4,3 %', 'no medible de frente'],
        ['Inicio de la fatiga detectado', 't = 57,3 s (ciclo 42)', 't = 57,8 s (ciclo 45)'],
        ['Causas principales según SHAP', 'apertura del hombro (173° → 151°), asimetría de brazos (3 % → 24 %), inclinación del tronco (2,7° → 7,9°)',
         'frecuencia (46,2 → 52,9 ciclos/min), asimetría de brazos (1 % → 23 %), alcance del brazo (−32 %)'],
        ['Estilo predicho', 'crol (98 %)', 'crol (95 %)'],
    ], 'Caso ficticio: resultados del sistema frente a la verdad de la simulación.', anchos=[5, 5.5, 5.5])
    w.p('El sistema detecta la fatiga al empezar la transición programada (aviso temprano, cuando el cambio aún es '
        'pequeño) y SHAP señala variables que de verdad se alteraron. Velocidad, frecuencia y distancia por ciclo siguen '
        'a la verdad (Figura 7). De frente no se mide la velocidad ni la inclinación, y los ángulos requieren el 3D.')
    w.figura(FIG / 'caso_verdad_vs_sistema.png', 'Caso ficticio (lateral): velocidad, frecuencia y distancia por ciclo medidas frente a la verdad.')
    w.p('**Clasificación del estilo.** Clasificador por ventanas de 4 s (bosque aleatorio) con rasgos que no dependen '
        'del estilo: brazos a la vez o alternos, posición de la nariz (boca abajo o arriba), piernas juntas o alternas, '
        'flexión máxima de rodilla, separación de pies, ondulación de la cadera y periodo de las manos. Con 64 vídeos '
        'simulados (4 estilos × 2 vistas × 8 nadadores) y validación agrupada por vídeo (GroupKFold) clasifica bien el '
        '100 % de los vídeos; SHAP muestra que la nariz separa crol y espalda, los brazos a la vez la mariposa y las '
        'piernas juntas la braza (Figura 8). Aplicado a los tres clips reales de Aaron no acierta: en vídeo real el '
        'modelo de pose copia brazos y piernas y la posición de la cabeza es menos marcada, así que hace falta '
        'entrenarlo con vídeos reales etiquetados de los cuatro estilos.')
    w.figura(FIG / 'caso_estilo.png', 'Clasificación del estilo en vídeos simulados: matriz de confusión y SHAP por estilo.')

    w.h3('Vídeo real: análisis completo de Aaron en crol')
    w.p('Se analizaron con `lote.py` los cinco clips de Aaron en crol: tres de GoPro bajo el agua en vista lateral '
        '(5120 × 2880, 30 fps) y dos de móvil en vista frontal (1080 × 1920, 60 fps). La vista frontal se identificó en '
        'los datos: en los clips de móvil el tronco aparece casi vertical en la imagen (78-102°) y mide 60-100 píxeles, '
        'frente a 8-10° en la GoPro, donde Aaron cruza la imagen de lado a lado (Tabla 7 y Figura 9).')
    w.tabla([
        ['Clip', 'Vista', 'Duración', 'Analizable', 'Ciclos', 'Ritmo (ciclos/min)'],
        ['GX011614', 'lateral', '46,2 s', '12,7 s', '9', '50,5'],
        ['GX011617', 'lateral', '29,0 s', '7,0 s', '0', '—'],
        ['GX011618', 'lateral', '28,2 s', '8,9 s', '1', '66,6'],
        ['IMG_7207', 'frontal', '6,0 s', '5,1 s', '3', '73,9'],
        ['IMG_7215', 'frontal', '9,4 s', '4,8 s', '4', '55,2'],
        ['**Total**', '', '**118,8 s**', '**38,5 s (32 %)**', '**17**', ''],
    ], 'Clips de Aaron en crol: tiempo analizable y ciclos válidos.', anchos=[2.8, 2.2, 2.4, 3.2, 2, 3.4])
    w.figura(FIG / 'aaron_clips.png', 'Aaron (crol): tiempo analizable y ciclos válidos por clip.', ancho_cm=14)
    w.p('El factor limitante es la detección: en GX011617 Aaron está en cuadro unos 19 s, pero el modelo de pose lo '
        'detecta en unos 5 s, la señal de la mano queda fragmentada y no se forman ciclos. La opción `--imgsz 1280` y '
        'el programa `probar_deteccion.py` permiten comprobar si una entrada mayor de la red recupera fotogramas; '
        'su evaluación sistemática queda como trabajo futuro.')

    w.h3('Validación del conteo de brazadas frente a la cuenta manual')
    w.tabla([
        ['Clip', 'Vista', 'Cuenta manual', 'Sistema', 'Error', 'Ciclos encontrados'],
        ['GX011614 (s 30-40)', 'lateral', '54 ciclos/min (9 ciclos en 10 s)', '50,5 ciclos/min', '−6,5 %', '—'],
        ['IMG_7207 (clip entero)', 'frontal', '80 ciclos/min (8 en 6,0 s)', '73,9 ciclos/min', '−7,6 %', '3 de 8'],
        ['IMG_7215 (clip entero)', 'frontal', '51 ciclos/min (8 en 9,4 s)', '55,2 ciclos/min', '+8,2 %', '4 de 8'],
    ], 'Validación frente a la cuenta manual de la autora. En GX011614, versiones previas del método, que distinguían '
       'brazo izquierdo y derecho, daban 79 y 34 ciclos/min.', anchos=[3.6, 1.9, 4, 2.7, 1.6, 2.2])
    w.p('El ritmo se mide con un error de entre el 6,5 % y el 8,2 % en las dos vistas, y el sistema distingue ritmos muy '
        'distintos del mismo nadador (80 y 51 ciclos/min). La cobertura es baja: de frente encuentra entre el 38 % y el '
        '50 % de los ciclos, por la detección parcial. Las tres comparaciones quedan como pruebas automáticas del código.')

    w.h3('Medidas de la técnica de Aaron')
    w.p('Las medidas se resumen solo con los clips laterales, porque los ángulos 2D de vistas distintas no son '
        'comparables (Tabla 9 y Figura 10). Izquierda y derecha se promedian, porque en vista lateral el modelo copia el '
        'brazo visible en el oculto.')
    w.tabla([
        ['Medida', 'Media', 'Desviación', 'Variación (CV)'],
        ['Frecuencia de ciclo', '52,1 ciclos/min', '11,6', '22 %'],
        ['Flexión del codo en el agarre', '125°', '16,6°', '13 %'],
        ['Apertura del hombro', '134°', '39,7°', '30 %'],
        ['Ángulo de cadera', '166°', '14,6°', '9 %'],
        ['Flexión de rodilla', '149°', '31,5°', '21 %'],
        ['Alcance del brazo', '2,08 troncos', '0,63', '30 %'],
        ['Inclinación del tronco', '8,5°', '4,1°', '49 %'],
        ['Amplitud de patada', '0,49 troncos', '0,29', '59 %'],
    ], 'Medidas por ciclo de Aaron en crol (10 ciclos laterales de GoPro).', anchos=[5.5, 3.5, 3, 3])
    w.figura(FIG / 'aaron_variables.png', 'Aaron (crol): valor de cada ciclo y mediana por clip.')
    w.p('La cadera a 166° y el tronco a 8,5° describen un cuerpo alineado y casi horizontal. Las variables de las '
        'piernas (rodilla y patada) son las más variables entre ciclos, lo que coincide con que son las peor detectadas '
        'bajo el agua; no deben leerse como cambios de técnica sin más datos.')

    w.h3('Fatiga en vídeo real')
    w.p('La sesión de GoPro reúne 10 ciclos y **no se detecta fatiga sostenida**; la del móvil reúne 7, por debajo del '
        'mínimo de 8 que exige el método. Es el resultado esperado: son pasadas de 10-20 s y el sistema no da una falsa '
        'alarma. En GX011614, sin fatiga, los valores SHAP son pequeños (≤ 0,1, frente a 0,4-0,6 en el nadador '
        'sintético) y se concentran en las piernas: explican la variabilidad de la detección, no un cambio técnico. '
        'Para localizar la fatiga en vídeo real hacen falta al menos unos 20 ciclos seguidos (25-30 s de nado continuo); '
        'el caso simulado muestra lo que el sistema entrega en esa situación.')

    w.h3('Validación del 3D frente al 2D')
    w.tabla([
        ['Ángulo', 'Mediana 2D', 'Mediana 3D', 'Correlación'],
        ['Codo izq. / dcho.', '156° / 144°', '158° / 143°', '0,51 / −0,08'],
        ['Hombro izq. / dcho.', '90° / 81°', '89° / 92°', '0,69 / 0,71'],
        ['Cadera izq. / dcha.', '171° / 172°', '160° / 164°', '0,58 / 0,69'],
        ['Rodilla izq. / dcha.', '173° / 173°', '107° / 106°', '0,01 / −0,04'],
    ], 'Ángulos 2D frente a 3D (MotionBERT) en la vista lateral de Aaron (85 fotogramas).', anchos=[4.5, 3.8, 3.8, 3.9])
    w.p('MotionBERT reconstruye mal las piernas de un nadador horizontal: coloca la rodilla a 107°, como si estuviera '
        'sentado, cuando la imagen la muestra casi extendida (173°), y comprime el rango del hombro. Por eso, en vista '
        'lateral los ángulos se calculan en 2D y el 3D se guarda aparte; en las vistas frontal y oblicua se usa el 3D.')


def cap5_discusion(w):
    w.p('Este capítulo compara el planteamiento inicial con el final y discute las decisiones y sus limitaciones.')
    w.h2('Respuesta a las indicaciones del director')
    w.tabla([
        ['Indicación', 'Cómo se ha incorporado'],
        ['La explicabilidad (SHAP) es lo más importante', 'SHAP es la salida principal: global, local y texto para el entrenador'],
        ['Dos verticales de IA: visión y tabular', 'Visión (pose 2D y 3D) y tabular (variables, fatiga y SHAP) con un formato intermedio común'],
        ['Modos diferenciados', 'Vídeo y tabular implementados; audio como trabajo futuro'],
        ['Modelo hidrodinámico como conocimiento previo', 'En el Capítulo 2; la potencia no es variable de los modelos'],
        ['Optimizar YOLO (MoveNet, ViTPose)', 'Comparativa en CPU; elegido YOLOv8n; MoveNet y MediaPipe como opción; ViTPose, trabajo futuro'],
    ], 'Indicaciones del director y su implementación.', anchos=[6, 10])
    w.h2('Cambios respecto al planteamiento inicial')
    w.vinetas([
        '**Solo vista lateral → lateral y frontal.** Parte de los vídeos se grabó de frente, donde la profundidad de la mano no se ve; se añadió una señal propia para esa vista.',
        '**MoveNet → YOLOv8n.** MoveNet se eligió por fluidez, pero la comparativa sobre vídeo subacuático mostró el doble de confianza con YOLO y cinco veces más ciclos válidos.',
        '**Sensores inerciales (IMU) → solo vídeo.** No se dispuso de sensores; la fusión con IMU queda como trabajo futuro.',
        '**LSTM supervisado → Isolation Forest no supervisado.** No hay etiquetas de fatiga; comparar al nadador con su propio estado fresco no las necesita y permite una explicación SHAP exacta.',
        '**Potencia en vatios → indicadores cinemáticos.** La potencia depende de C_D y A, no medibles desde vídeo.',
        '**Validación por fotograma → validación por vídeo.** El 99,99 % de precisión anterior era fuga de datos.',
        '**Colab con GPU → portátil en CPU.** Para un uso real en un club, sin coste y sin subir los vídeos.',
    ])
    w.h2('Limitaciones')
    w.vinetas([
        'Una sola cámara: los ángulos 2D son proyecciones; la refracción y la rotación del cuerpo los distorsionan.',
        'En vista lateral el modelo no distingue el brazo izquierdo del derecho: la asimetría y el codo de cada lado son poco fiables en esta vista.',
        'Detección parcial: con YOLOv8n en CPU, el nadador es analizable en torno a un tercio del vídeo y, de frente, se encuentran entre el 38 % y el 50 % de los ciclos.',
        'La vista (lateral o frontal) la indica el usuario en la lista de vídeos; si se equivoca, el conteo empeora (con la señal frontal en un clip lateral el error pasó del 6,5 % al 14 %).',
        'Los clips disponibles son pasadas cortas: no permiten observar la fatiga en vídeo real.',
        'La clasificación del estilo solo está validada con vídeos simulados; con vídeo real falla y necesita vídeos etiquetados.',
        'La fase base supone que el nadador empieza fresco; si llega fatigado, el inicio se subestima.',
        'Falta contrastar el momento de fatiga con una referencia independiente (lactato, esfuerzo percibido o entrenador).',
        'Los resultados reales corresponden a un nadador; la extensión a los 8 nadadores queda como trabajo futuro.',
    ])


def cap6_trabajo(w):
    w.p('Se ha desarrollado un sistema completo que funciona en la CPU de un portátil y que convierte un vídeo de nado '
        'en eficiencia, momento de fatiga y explicación por variable. Con datos sintéticos, de lado y de frente, la '
        'detección de fatiga y la explicación SHAP recuperan la transición y las variables introducidas. Con vídeo '
        'real, el conteo de brazadas se aleja entre un 6,5 % y un 8,2 % de la cuenta manual en tres clips y dos vistas, '
        'y las medidas de Aaron describen un crol con el cuerpo alineado. La comparativa sobre el propio vídeo '
        'subacuático resultó más útil que las métricas de COCO para elegir el modelo de pose, y la validación del 3D '
        'mostró dónde se puede confiar en él. En los clips reales disponibles no se detecta fatiga, lo que es coherente '
        'con pasadas cortas; el factor limitante es la detección del nadador y la duración del nado continuo, no el '
        'método de fatiga, que en el caso simulado localiza el inicio de la fatiga y explica sus causas.')


def cap6_personales(w):
    w.p('Este trabajo me ha enseñado que, en un proyecto de IA aplicada, la calidad de los datos pesa más que la '
        'elección del modelo. Descubrir que el 99,99 % de precisión de una versión anterior era fuga de datos fue la '
        'lección más importante: desde entonces he validado cada resultado frente a una referencia, ya fuera una cuenta '
        'manual o un caso simulado con verdad conocida.')
    w.p('También he aprendido a adaptar herramientas pensadas para personas de pie a un entorno tan distinto como el '
        'agua, y a explicar los resultados de forma que un entrenador pueda usarlos. Trabajar con un portátil sin GPU '
        'me obligó a priorizar soluciones ligeras y a medir su coste real. Me llevo, sobre todo, la importancia de ser '
        'honesta con lo que el sistema puede y no puede afirmar.')


def cap7_futuro(w):
    w.vinetas([
        'Analizar los 8 nadadores y comparar sus patrones de fatiga.',
        'Entrenar el clasificador de estilo con vídeos reales etiquetados de los cuatro estilos.',
        'Detectar la vista (lateral o frontal) automáticamente a partir de la orientación del tronco.',
        'Ajustar el modelo de pose con imágenes subacuáticas etiquetadas (SwimXYZ y fotogramas propios) para distinguir los dos brazos y detectar más fotogramas.',
        'Adaptar MotionBERT a natación para obtener ángulos 3D fiables en las piernas.',
        'Evaluar ViTPose cuando se disponga de GPU.',
        'Modo audio: frecuencia de brazada y respiración a partir del sonido.',
        'Fusión con sensores inerciales (IMU) para medir la velocidad sin calibrar la cámara.',
        'Validar el inicio de la fatiga frente a lactato, esfuerzo percibido y valoración del entrenador.',
        'Grabar sesiones con una cámara que siga al nadador para analizar nado continuo.',
    ])


def anexos(w):
    w.h2('Anexo A. Guía de ejecución')
    for t in ['pip install -r requirements.txt',
              'python diagnostico.py',
              'python analizar.py "videos/GX011614.MP4" --nadador "Aaron"',
              'python analizar.py "videos/GX011614.MP4" --comparativa',
              'python sesion.py resultados/GX011614 resultados/GX011617 resultados/GX011618 --nadador "Aaron"',
              'python lote.py --carpeta videos --crear-lista      (y después sin --crear-lista)',
              'python informe_nadador.py resultados --nadador Aaron --estilo crol',
              'python probar_deteccion.py "videos/GX011617.MP4" --desde 9 --hasta 29']:
        w.p(t, alinear='izq', size=9)
    w.p('Salidas en la carpeta de resultados: keypoints_raw.npz, keypoints_3d.npy, medidas_por_fotograma.csv, '
        'variables_por_ciclo.csv, shap_por_ciclo.csv, resumen.json, figuras fig_*.png y video_anotado.mp4.')
    w.h2('Anexo B. Estructura del código')
    w.tabla([
        ['Archivo', 'Función'],
        ['analizar.py', 'Programa principal: pose, limpieza, 3D, medidas, fatiga y vídeo'],
        ['strokelab/pose.py', 'Modelos de pose (YOLO, MoveNet, MediaPipe), giro y comparativa'],
        ['strokelab/lift3d.py', 'Elevación a 3D con MotionBERT adaptada a nadadores'],
        ['strokelab/medidas.py', 'Limpieza, filtros anatómicos, ángulos, ciclos y variables'],
        ['strokelab/fatiga.py', 'Isolation Forest, PELT, SHAP y explicación en texto'],
        ['strokelab/video.py', 'Vídeo anotado con el panel de fatiga'],
        ['sesion.py', 'Fatiga a lo largo de varias pasadas'],
        ['lote.py', 'Análisis de todos los vídeos de una carpeta y de sus sesiones'],
        ['informe_nadador.py', 'Informe de un nadador y un estilo'],
        ['probar_deteccion.py', 'Comparación de ajustes de YOLO en el tramo con nadador'],
        ['validar_3d.py', 'Comparación de ángulos 2D y 3D'],
    ], 'Módulos del código de StrokeLab.', anchos=[5, 11])
    w.h2('Anexo C. Pruebas automáticas')
    w.vinetas([
        'tests/test_local.py: nadador sintético con errores típicos; exige detectar la fatiga entre 40 y 60 s y medidas plausibles.',
        'tests/test_sesion.py: el nadador sintético partido en pasadas, con una pasada vacía.',
        'tests/test_aaron.py: datos reales de Aaron; exige una frecuencia a menos de un 15 % de la cuenta manual.',
        'tests/test_movenet_recorte.py: conversión de coordenadas del recorte de MoveNet.',
        'tests/test_estilos.py: ciclos de mariposa (1 brazada) y crol (2 brazadas).',
        'tests/test_frontal.py: nadador sintético visto de frente, con fatiga.',
        'tests/test_aaron_frontal.py: clips de móvil de Aaron; exige una frecuencia a menos de un 15 % de la cuenta manual.',
        'tests/test_lote.py: lista de vídeos, análisis por lotes y sesión.',
    ])


# ---------------------------------------------------------------- montaje

def main():
    doc = docx.Document(str(PLANTILLA))
    if 'Caption' not in [s.name for s in doc.styles]:
        st = doc.styles.add_style('Caption', 1)
        st.base_style = doc.styles['Normal']
        st.font.size = Pt(9); st.font.italic = True
        st.paragraph_format.space_after = Pt(8)
    b = list(doc.element.body.iterchildren())
    P = lambda i: Paragraph(b[i], doc._body)  # noqa: E731
    ppr_vineta = copy.deepcopy(b[64].find(qn('w:pPr')))
    for e in ppr_vineta.findall(qn('w:rPr')):
        ppr_vineta.remove(e)
    ppr_h2 = copy.deepcopy(b[177].find(qn('w:pPr')))

    # portada
    poner_texto(P(8), 'MÁSTER UNIVERSITARIO EN INTELIGENCIA ARTIFICIAL')
    poner_texto(P(11), TITULO, size=16)
    poner_texto(P(13), AUTORA)
    poner_texto(P(14), 'Dirigido por')
    poner_texto(P(15), DIRECTOR)
    poner_texto(P(16), 'CURSO 2025-2026')
    poner_texto(P(17), f'TÍTULO: {TITULO}')
    poner_texto(P(19), f'AUTOR: {AUTORA}')
    poner_texto(P(21), 'TITULACIÓN: Máster Universitario en Inteligencia Artificial')
    poner_texto(P(23), f'DIRECTOR/ES DEL PROYECTO: {DIRECTOR}')
    poner_texto(P(26), 'FECHA: octubre de 2026')

    # encabezados de página
    for s in doc.sections:
        for h in (s.header, s.first_page_header, s.even_page_header):
            for par in h.paragraphs:
                if 'Título Proyecto' in par.text:
                    poner_texto(par, TITULO_CORTO)
                elif 'Apellido1' in par.text:
                    poner_texto(par, 'Diana Cruz')

    # tabla resumen
    t = Table(b[128], doc._body)
    for fila, txt in zip(range(1, 8), [AUTORA, TITULO, DIRECTOR, 'NO', 'SÍ', 'SÍ',
                                       'Desarrollar un sistema de IA explicable que, a partir de vídeo, cuantifique la '
                                       'eficiencia de la brazada, localice el inicio de la fatiga y explique sus causas con SHAP.']):
        poner_texto(t.cell(fila, 1).paragraphs[0], txt)

    # presupuesto
    t = Table(b[246], doc._body)
    for fila, (valor, com) in zip(range(1, 6), [
            ('300 h · 6.000 €', 'Estimación: 12 ECTS × 25 h, valoradas a 20 €/h'),
            ('1.200 €', 'Valor aproximado de mercado del portátil (800 €) y de la cámara GoPro (400 €)'),
            ('0 €', 'Software libre: Python, PyTorch, Ultralytics, OpenCV, scikit-learn, shap, XGBoost, Git; Google Colab gratuito'),
            ('0 €', 'Artículos de acceso abierto o a través de la biblioteca de la UEM'),
            ('0 €', 'Sin sensores ni material adicional')]):
        poner_texto(t.cell(fila, 1).paragraphs[0], valor)
        poner_texto(t.cell(fila, 2).paragraphs[0], com)
        for extra in t.cell(fila, 2).paragraphs[1:]:
            borrar(extra._p)

    # secciones: (índice del título, índices de la guía a borrar, función que escribe el contenido)
    secciones = [
        (177, [178], cap1_contexto), (179, [180, 181], cap1_problema), (182, [183], cap1_objetivos),
        (184, [185], cap1_resultados), (186, [187], cap1_estructura),
        (193, [194, 195], cap2_estado), (196, range(197, 203), cap2_contexto), (203, [204, 205], cap2_problema),
        (209, range(210, 219), cap3_generales), (219, range(220, 227), cap3_especificos), (227, [228], cap3_beneficios),
        (232, [233, 234], cap4_planificacion), (235, [236, 237, 238], cap4_solucion), (239, [240], cap4_recursos),
        (241, [242, 243, 244, 245], cap4_presupuesto), (247, [248], cap4_viabilidad), (249, [250, 251, 252], cap4_resultados),
        (253, [254, 255, 256], cap5_discusion), (259, [260], cap6_trabajo), (262, [263], cap6_personales),
        (268, [269], cap7_futuro), (288, [289], anexos),
    ]
    for h, guia, fn in secciones:
        fn(Escritor(doc, b[h], ppr_vineta, ppr_h2))
    # El presupuesto: el texto va antes de la tabla (ya queda así porque se inserta tras el título)

    # resumen y abstract
    w = Escritor(doc, b[99], ppr_vineta, ppr_h2)
    w.p(RESUMEN)
    w.p(f'**Palabras clave:** {PALABRAS_CLAVE}', alinear='izq')
    w = Escritor(doc, b[112], ppr_vineta, ppr_h2)
    w.p(ABSTRACT)
    w.p(f'**Keywords:** {KEYWORDS}', alinear='izq')
    poner_texto(P(118), 'Gracias a mi director/a por su orientación, al club y a los nadadores que se dejaron grabar, y a mi familia por su apoyo durante el máster.')

    # índices de figuras y tablas
    for h, guia, tipo in [(165, [166], 'Figura'), (170, [171], 'Tabla')]:
        par = Escritor(doc, b[h], ppr_vineta, ppr_h2).p('', alinear='izq')
        campo(par, f'TOC \\h \\z \\c "{tipo}"', 'Actualizar campos (F9) para generar el índice.')

    # referencias
    w = Escritor(doc, b[270], ppr_vineta, ppr_h2)
    for ref in REFERENCIAS:
        par = w.p(ref, estilo='Bibliography', alinear='izq')
        par.paragraph_format.left_indent = Cm(1)
        par.paragraph_format.first_line_indent = Cm(-1)
        par.paragraph_format.space_after = Pt(4)

    # borrar instrucciones y textos guía (índices de la plantilla original)
    a_borrar = set(range(29, 97)) | set(range(100, 111)) | {113, 115} | set(range(119, 125)) | {127, 132} \
        | {24, 28, 97, 98} | set(range(290, 301)) | {166, 171} | {175, 176} | {192} | {207, 208} | set(range(271, 287)) | {287} | {301}
    for h, guia, fn in secciones:
        a_borrar |= set(guia)
    for i in sorted(a_borrar, reverse=True):
        borrar(b[i])

    # pedir a Word que actualice índices y números al abrir
    ajustes = doc.settings.element
    uf = ajustes.find(qn('w:updateFields'))
    if uf is None:
        uf = OxmlElement('w:updateFields'); ajustes.append(uf)
    uf.set(qn('w:val'), 'true')

    doc.save(str(SALIDA))
    print(f'Generado: {SALIDA}')


if __name__ == '__main__':
    main()
