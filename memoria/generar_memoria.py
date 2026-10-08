"""Rellena la plantilla de memoria de la UEM con el contenido del TFM StrokeLab.

Uso:  python memoria/generar_memoria.py
Salida: memoria/TFM_StrokeLab_borrador.docx y, si LibreOffice está instalado, memoria/TFM_StrokeLab_final.docx
(índices, índice de figuras, de tablas y de ecuaciones ya calculados).

El texto vive en este archivo. Marcado:
  **negrita**, *cursiva*, `código`, _{subíndice}, ^{superíndice};
  [@clave] o [@a; @b]  -> cita numerada [n] con enlace a la referencia (orden de primera aparición, estilo IEEE);
  {fig:x}, {tab:x}, {eq:x} -> número de la figura, tabla o ecuación con esa etiqueta.
  «StrokeLab» se escribe siempre en cursiva (nombre propio).
Se generan dos pasadas: la primera fija el orden de las citas y los números de figuras, tablas y ecuaciones.
"""
import copy
import re
import shutil
import subprocess
import sys
from pathlib import Path

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from docx.table import Table
from docx.text.paragraph import Paragraph
from lxml import etree

AQUI = Path(__file__).resolve().parent
PLANTILLA = AQUI / 'Plantilla_memoria_TFM.docx'
SALIDA = AQUI / 'TFM_StrokeLab_borrador.docx'
FINAL = AQUI / 'TFM_StrokeLab_final.docx'
FIG = AQUI / 'figuras'

TITULO = ('StrokeLab: desarrollo de un sistema de análisis biomecánico explicable para la evaluación de la técnica '
          'y la fatiga en natación mediante visión por computador e inteligencia artificial')
TITULO_CORTO = 'StrokeLab: análisis biomecánico explicable de la técnica y la fatiga en natación'
AUTORA = 'Diana Cruz'
DIRECTOR = '______________________________'
AZUL_ENLACE = '1F4E79'
M_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/math'

# Estado compartido entre las dos pasadas
EST = dict(citas=[], citas_pasada=[], num={}, cont={}, marcador=100)


# ---------------------------------------------------------------- referencias (estilo IEEE)

REFS = {
    'craig1979': 'A. B. Craig y D. R. Pendergast, «Relationships of stroke rate, distance per stroke, and velocity in competitive swimming», *Medicine and Science in Sports*, vol. 11, n.º 3, pp. 278-283, 1979.',
    'costill1985': 'D. L. Costill, J. Kovaleski, D. Porter, J. Kirwan, R. Fielding y D. King, «Energy expenditure during front crawl swimming: predicting success in middle-distance events», *International Journal of Sports Medicine*, vol. 6, n.º 5, pp. 266-270, 1985.',
    'toussaint1992': 'H. M. Toussaint y P. J. Beek, «Biomechanics of competitive front crawl swimming», *Sports Medicine*, vol. 13, n.º 1, pp. 8-24, 1992.',
    'chollet2000': 'D. Chollet, S. Chalies y J. C. Chatard, «A new index of coordination for the crawl: description and usefulness», *International Journal of Sports Medicine*, vol. 21, n.º 1, pp. 54-59, 2000.',
    'alberty2005': 'M. Alberty, M. Sidney, F. Huot-Marchand, J. M. Hespel y P. Pelayo, «Intracyclic velocity variations and arm coordination during exhaustive exercise in front crawl stroke», *International Journal of Sports Medicine*, vol. 26, n.º 6, pp. 471-475, 2005.',
    'lecun2015': 'Y. LeCun, Y. Bengio y G. Hinton, «Deep learning», *Nature*, vol. 521, n.º 7553, pp. 436-444, 2015.',
    'redmon2016': 'J. Redmon, S. Divvala, R. Girshick y A. Farhadi, «You only look once: unified, real-time object detection», en *Proc. IEEE Conference on Computer Vision and Pattern Recognition (CVPR)*, 2016, pp. 779-788.',
    'pan2010': 'S. J. Pan y Q. Yang, «A survey on transfer learning», *IEEE Transactions on Knowledge and Data Engineering*, vol. 22, n.º 10, pp. 1345-1359, 2010.',
    'lin2014': 'T.-Y. Lin et al., «Microsoft COCO: common objects in context», en *European Conference on Computer Vision (ECCV)*, 2014, pp. 740-755.',
    'cao2017': 'Z. Cao, T. Simon, S.-E. Wei y Y. Sheikh, «Realtime multi-person 2D pose estimation using part affinity fields», en *Proc. IEEE CVPR*, 2017, pp. 7291-7299.',
    'sun2019': 'K. Sun, B. Xiao, D. Liu y J. Wang, «Deep high-resolution representation learning for human pose estimation», en *Proc. IEEE CVPR*, 2019, pp. 5693-5703.',
    'maji2022': 'D. Maji, S. Nagori, M. Mathew y D. Poddar, «YOLO-Pose: enhancing YOLO for multi person pose estimation using object keypoint similarity loss», en *Proc. IEEE CVPR Workshops*, 2022.',
    'jocher2023': 'G. Jocher, A. Chaurasia y J. Qiu, *Ultralytics YOLOv8* (software y documentación de modelos), GitHub, 2023.',
    'google2021': 'Google, *MoveNet: ultra fast and accurate pose detection model*, TensorFlow Hub, 2021.',
    'bazarevsky2020': 'V. Bazarevsky, I. Grishchenko, K. Raveendran, T. Zhu, F. Zhang y M. Grundmann, «BlazePose: on-device real-time body pose tracking», arXiv:2006.10204, 2020.',
    'vaswani2017': 'A. Vaswani et al., «Attention is all you need», en *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 30, 2017.',
    'xu2022': 'Y. Xu, J. Zhang, Q. Zhang y D. Tao, «ViTPose: simple vision transformer baselines for human pose estimation», en *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 35, 2022.',
    'andriluka2014': 'M. Andriluka, L. Pishchulin, P. Gehler y B. Schiele, «2D human pose estimation: new benchmark and state of the art analysis», en *Proc. IEEE CVPR*, 2014, pp. 3686-3693.',
    'martinez2017': 'J. Martinez, R. Hossain, J. Romero y J. J. Little, «A simple yet effective baseline for 3D human pose estimation», en *Proc. IEEE International Conference on Computer Vision (ICCV)*, 2017, pp. 2640-2649.',
    'ionescu2014': 'C. Ionescu, D. Papava, V. Olaru y C. Sminchisescu, «Human3.6M: large scale datasets and predictive methods for 3D human sensing in natural environments», *IEEE Transactions on Pattern Analysis and Machine Intelligence*, vol. 36, n.º 7, pp. 1325-1339, 2014.',
    'zhu2023': 'W. Zhu, X. Ma, Z. Liu, L. Liu, W. Wu e Y. Wang, «MotionBERT: a unified perspective on learning human motion representations», en *Proc. IEEE/CVF ICCV*, 2023, pp. 15085-15099.',
    'einfalt2018': 'M. Einfalt, D. Zecha y R. Lienhart, «Activity-conditioned continuous human pose estimation for performance analysis of athletes using the example of swimming», en *Proc. IEEE Winter Conference on Applications of Computer Vision (WACV)*, 2018, pp. 446-455.',
    'fiche2023': 'G. Fiche, V. Sevestre, C. Gonzalez-Barral, S. Leglaive y R. Séguier, «SwimXYZ: a large-scale dataset of synthetic swimming motions and videos», en *ACM SIGGRAPH Conference on Motion, Interaction and Games (MIG)*, 2023.',
    'chandola2009': 'V. Chandola, A. Banerjee y V. Kumar, «Anomaly detection: a survey», *ACM Computing Surveys*, vol. 41, n.º 3, art. 15, 2009.',
    'liu2008': 'F. T. Liu, K. M. Ting y Z.-H. Zhou, «Isolation forest», en *Proc. IEEE International Conference on Data Mining (ICDM)*, 2008, pp. 413-422.',
    'killick2012': 'R. Killick, P. Fearnhead e I. A. Eckley, «Optimal detection of changepoints with a linear computational cost», *Journal of the American Statistical Association*, vol. 107, n.º 500, pp. 1590-1598, 2012.',
    'breiman2001': 'L. Breiman, «Random forests», *Machine Learning*, vol. 45, n.º 1, pp. 5-32, 2001.',
    'kaufman2012': 'S. Kaufman, S. Rosset, C. Perlich y O. Stitelman, «Leakage in data mining: formulation, detection, and avoidance», *ACM Transactions on Knowledge Discovery from Data*, vol. 6, n.º 4, art. 15, 2012.',
    'chen2016': 'T. Chen y C. Guestrin, «XGBoost: a scalable tree boosting system», en *Proc. 22nd ACM SIGKDD Conference on Knowledge Discovery and Data Mining*, 2016, pp. 785-794.',
    'shapley1953': 'L. S. Shapley, «A value for n-person games», en *Contributions to the Theory of Games II*, Annals of Mathematics Studies 28, Princeton University Press, 1953, pp. 307-317.',
    'lundberg2017': 'S. M. Lundberg y S.-I. Lee, «A unified approach to interpreting model predictions», en *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 30, 2017, pp. 4765-4774.',
    'lundberg2020': 'S. M. Lundberg et al., «From local explanations to global understanding with explainable AI for trees», *Nature Machine Intelligence*, vol. 2, pp. 56-67, 2020.',
    'savitzky1964': 'A. Savitzky y M. J. E. Golay, «Smoothing and differentiation of data by simplified least squares procedures», *Analytical Chemistry*, vol. 36, n.º 8, pp. 1627-1639, 1964.',
    'jolliffe2016': 'I. T. Jolliffe y J. Cadima, «Principal component analysis: a review and recent developments», *Philosophical Transactions of the Royal Society A*, vol. 374, n.º 2065, 20150202, 2016.',
}


# ---------------------------------------------------------------- utilidades de formato

def _run_xml(texto, size=None, italic=False, bold=False, color=None, vert=None, mono=False):
    r = OxmlElement('w:r')
    rpr = OxmlElement('w:rPr')
    if mono:
        f = OxmlElement('w:rFonts'); f.set(qn('w:ascii'), 'Consolas'); f.set(qn('w:hAnsi'), 'Consolas'); rpr.append(f)
    if bold:
        rpr.append(OxmlElement('w:b'))
    if italic:
        rpr.append(OxmlElement('w:i'))
    if color:
        c = OxmlElement('w:color'); c.set(qn('w:val'), color); rpr.append(c)
    if size:
        s = OxmlElement('w:sz'); s.set(qn('w:val'), str(int(size * 2))); rpr.append(s)
    if vert:
        v = OxmlElement('w:vertAlign'); v.set(qn('w:val'), vert); rpr.append(v)
    if len(rpr):
        r.append(rpr)
    if texto == '\t':
        r.append(OxmlElement('w:tab'))
        return r
    t = OxmlElement('w:t'); t.set(qn('xml:space'), 'preserve'); t.text = texto
    r.append(t)
    return r


def _num_ref(tipo, clave):
    return str(EST['num'].get((tipo, clave), '?'))


def _cita(par, claves, size):
    numeros = []
    for k in claves:
        assert k in REFS, f'referencia desconocida: {k}'
        if k not in EST['citas_pasada']:
            EST['citas_pasada'].append(k)
        n = EST['citas'].index(k) + 1 if k in EST['citas'] else 0
        numeros.append((n, k))
    par._p.append(_run_xml('[', size))
    for i, (n, k) in enumerate(sorted(numeros)):
        if i:
            par._p.append(_run_xml(', ', size))
        h = OxmlElement('w:hyperlink'); h.set(qn('w:anchor'), f'ref_{k}'); h.set(qn('w:history'), '1')
        h.append(_run_xml(str(n or '?'), size, color=AZUL_ENLACE))
        par._p.append(h)
    par._p.append(_run_xml(']', size))


TOKENS = re.compile(r'(\*\*.+?\*\*|\*[^*\n]+?\*|`[^`]+`|\[@[^\]]+\]|\{(?:fig|tab|eq):[a-z0-9_]+\}|_\{[^}]*\}|\^\{[^}]*\}|\[PENDIENTE[^\]]*\])')


def _texto_plano(par, texto, size, bold=False):
    """Texto normal; «StrokeLab» siempre en cursiva."""
    for trozo in re.split(r'(StrokeLab)', texto):
        if trozo:
            par._p.append(_run_xml(trozo, size, italic=trozo == 'StrokeLab', bold=bold))


def runs_con_formato(p, texto, size=None):
    for trozo in TOKENS.split(texto):
        if not trozo:
            continue
        if trozo.startswith('**'):
            _texto_plano(p, trozo[2:-2], size, bold=True)
        elif trozo.startswith('[PENDIENTE'):
            p._p.append(_run_xml(trozo, size, bold=True, color='C00000'))
        elif trozo.startswith('`'):
            p._p.append(_run_xml(trozo[1:-1], size, mono=True))
        elif trozo.startswith('[@'):
            _cita(p, [c.strip().lstrip('@') for c in trozo[1:-1].split(';')], size)
        elif trozo.startswith('{'):
            tipo, clave = trozo[1:-1].split(':')
            p._p.append(_run_xml(_num_ref(tipo, clave), size))
        elif trozo.startswith('_{'):
            p._p.append(_run_xml(trozo[2:-1], size, vert='subscript'))
        elif trozo.startswith('^{'):
            p._p.append(_run_xml(trozo[2:-1], size, vert='superscript'))
        elif trozo.startswith('*') and len(trozo) > 2:
            p._p.append(_run_xml(trozo[1:-1], size, italic=True))
        else:
            _texto_plano(p, trozo, size)


def poner_texto(p, texto, size=None):
    """Sustituye el texto de un párrafo de la plantilla conservando el formato de su primer run, en negro."""
    runs = p.runs
    rpr = copy.deepcopy(runs[0]._r.rPr) if runs and runs[0]._r.rPr is not None else None
    for r in runs:
        r._r.getparent().remove(r._r)
    antes = len(p._p.findall(qn('w:r')))
    runs_con_formato(p, texto, size)
    for r in p._p.findall(qn('w:r'))[antes:]:
        propio = r.find(qn('w:rPr'))
        nuevo = copy.deepcopy(rpr) if rpr is not None else OxmlElement('w:rPr')
        for tag in ('w:color', 'w:i', 'w:sz', 'w:szCs'):
            for e in nuevo.findall(qn(tag)):
                if tag in ('w:color', 'w:i') or (propio is not None and propio.find(qn(tag)) is not None):
                    nuevo.remove(e)
        if propio is not None:
            for e in propio:
                nuevo.append(e)
            r.remove(propio)
        if nuevo.find(qn('w:color')) is None:
            c = OxmlElement('w:color'); c.set(qn('w:val'), '000000'); nuevo.append(c)
        r.insert(0, nuevo)


# ---------------------------------------------------------------- ecuaciones (OMML, editables en Word)

def _m(tag, padre=None, **attrs):
    e = etree.SubElement(padre, f'{{{M_NS}}}{tag}') if padre is not None else etree.Element(f'{{{M_NS}}}{tag}', nsmap={'m': M_NS})
    for k, v in attrs.items():
        e.set(f'{{{M_NS}}}{k}', v)
    return e


GRIEGAS = set('αβγδεζηθικλμνξπρστυφχψωΔΣΦΩΓΛΠΘ')


def _om(x, padre):
    """Construye OMML: str (texto), lista (concatenación) o tupla (operador)."""
    if isinstance(x, list):
        for y in x:
            _om(y, padre)
        return
    if isinstance(x, str):
        if not x:
            return
        r = _m('r', padre)
        if len(x) > 1 and x.isalpha() and not set(x) <= GRIEGAS:          # palabras (exp, arccos, mín): rectas
            rp = _m('rPr', r); _m('sty', rp, val='p')
        t = _m('t', r); t.text = x
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        return
    op = x[0]
    if op in ('sub', 'sup'):
        e = _m('sSub' if op == 'sub' else 'sSup', padre)
        _om(x[1], _m('e', e)); _om(x[2], _m(op, e))
    elif op == 'subsup':
        e = _m('sSubSup', padre)
        _om(x[1], _m('e', e)); _om(x[2], _m('sub', e)); _om(x[3], _m('sup', e))
    elif op == 'frac':
        e = _m('f', padre)
        _om(x[1], _m('num', e)); _om(x[2], _m('den', e))
    elif op in ('sum', 'int'):
        e = _m('nary', padre)
        pr = _m('naryPr', e); _m('chr', pr, val='∑' if op == 'sum' else '∫')
        _m('limLoc', pr, val='undOvr' if op == 'sum' else 'subSup')
        if x[2] is None:
            _m('supHide', pr, val='1')
        _om(x[1] or '', _m('sub', e)); _om(x[2] or '', _m('sup', e)); _om(x[3], _m('e', e))
    elif op in ('par', 'bar', 'norm', 'cor', 'llave'):
        e = _m('d', padre)
        pr = _m('dPr', e)
        par = {'par': ('(', ')'), 'bar': ('|', '|'), 'norm': ('‖', '‖'), 'cor': ('[', ']'), 'llave': ('{', '}')}[op]
        _m('begChr', pr, val=par[0]); _m('endChr', pr, val=par[1])
        _om(x[1], _m('e', e))
    elif op == 'acc':
        e = _m('acc', padre)
        pr = _m('accPr', e); _m('chr', pr, val=x[2])
        _om(x[1], _m('e', e))
    elif op == 'media':                                     # raya superior (media)
        e = _m('bar', padre)
        pr = _m('barPr', e); _m('pos', pr, val='top')
        _om(x[1], _m('e', e))
    else:
        raise ValueError(op)


def omml(expr):
    para = _m('oMathPara')
    _om(expr, _m('oMath', para))
    return para


# ---------------------------------------------------------------- escritor de bloques

class Escritor:
    """Inserta bloques de contenido uno detrás de otro a partir de un elemento de la plantilla."""

    def __init__(self, doc, ancla, ppr_vineta):
        self.doc, self.ultimo, self.ppr_vineta = doc, ancla, ppr_vineta

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
            par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    def h2(self, texto):
        self.p(texto, estilo='Heading 2', alinear='izq').paragraph_format.keep_with_next = True

    def h3(self, texto):
        self.p(texto, estilo='Heading 3', alinear='izq').paragraph_format.keep_with_next = True

    def leyenda(self, tipo, texto, clave=None):
        """Leyenda con número automático (campo SEQ), para los índices de figuras, tablas y ecuaciones."""
        n = EST['cont'][tipo] = EST['cont'].get(tipo, 0) + 1
        if clave:
            EST['num'][({'Figura': 'fig', 'Tabla': 'tab', 'Ecuación': 'eq'}[tipo], clave)] = n
        par = self.p('', estilo='Caption', alinear='centro')
        par._p.append(_run_xml(f'{tipo} '))
        campo(par, f'SEQ {tipo} \\* ARABIC', str(n))
        par._p.append(_run_xml('. '))
        runs_con_formato(par, texto)
        return par

    def figura(self, ruta, texto, clave=None, ancho_cm=15):
        par = self.p('', alinear='centro')
        par.paragraph_format.keep_with_next = True
        par.add_run().add_picture(str(ruta), width=Cm(ancho_cm))
        self.leyenda('Figura', texto, clave)

    def tabla(self, filas, texto, clave=None, anchos=None, size=9):
        """filas[0] = cabecera. La leyenda va encima. La tabla no se parte entre páginas."""
        cap = self.leyenda('Tabla', texto, clave)
        cap.paragraph_format.keep_with_next = True
        t = self.doc.add_table(rows=len(filas), cols=len(filas[0]))
        t.style = self.doc.styles['Table Grid']
        for i, fila in enumerate(filas):
            trpr = t.rows[i]._tr.get_or_add_trPr()
            trpr.append(OxmlElement('w:cantSplit'))
            if i == 0:
                trpr.append(OxmlElement('w:tblHeader'))
            for j, txt in enumerate(fila):
                celda = t.cell(i, j)
                par = celda.paragraphs[0]
                par.paragraph_format.space_before = Pt(1)
                par.paragraph_format.space_after = Pt(1)
                par.paragraph_format.keep_with_next = i < len(filas) - 1
                runs_con_formato(par, str(txt), size)
                if i == 0:
                    for r in par._p.iter(qn('w:r')):
                        rp = r.find(qn('w:rPr'))
                        if rp is None:
                            rp = OxmlElement('w:rPr'); r.insert(0, rp)
                        rp.insert(0, OxmlElement('w:b'))
                    sombra = OxmlElement('w:shd')
                    sombra.set(qn('w:val'), 'clear'); sombra.set(qn('w:color'), 'auto'); sombra.set(qn('w:fill'), 'D9E2F3')
                    celda._tc.get_or_add_tcPr().append(sombra)
                if anchos:
                    celda.width = Cm(anchos[j])
        if anchos:                                  # rejilla con los mismos anchos (LibreOffice la usa)
            for gc, a in zip(t._tbl.tblGrid.findall(qn('w:gridCol')), anchos):
                gc.set(qn('w:w'), str(int(Cm(a).twips)))
        self._poner(t._tbl)
        self.p('', size=4)

    def ecuacion(self, clave, expr, titulo, simbolos=None):
        """Ecuación de Word numerada, con título y lista de símbolos (significado y unidades)."""
        par = self.p('', alinear='centro')
        par.paragraph_format.keep_with_next = True
        par._p.append(omml(expr))
        cap = self.leyenda('Ecuación', titulo, clave)
        if simbolos:
            cap.paragraph_format.keep_with_next = True
            self.p('donde:', alinear='izq').paragraph_format.keep_with_next = True
            for i, (s, d) in enumerate(simbolos):
                par = self.p(f'{s}: {d}', alinear='izq')
                par._p.insert(0, copy.deepcopy(self.ppr_vineta))
                par.paragraph_format.keep_with_next = i < len(simbolos) - 1


def campo(par, instr, texto_previo=''):
    """Inserta un campo de Word (SEQ, TOC...) en el párrafo."""
    def fc(tipo):
        r = OxmlElement('w:r'); f = OxmlElement('w:fldChar'); f.set(qn('w:fldCharType'), tipo); r.append(f); return r
    par._p.append(fc('begin'))
    r = OxmlElement('w:r'); it = OxmlElement('w:instrText'); it.set(qn('xml:space'), 'preserve'); it.text = f' {instr} '
    r.append(it); par._p.append(r)
    par._p.append(fc('separate'))
    par._p.append(_run_xml(texto_previo))
    par._p.append(fc('end'))


def borrar(elem):
    elem.getparent().remove(elem)


# ---------------------------------------------------------------- resumen

RESUMEN = (
    'La evaluación de la técnica de nado y de la aparición de la fatiga se basa habitualmente en la observación '
    'subjetiva del entrenador o en sistemas instrumentados de coste elevado. Este trabajo presenta StrokeLab, un '
    'sistema de análisis biomecánico explicable que, a partir de vídeo monocular convencional, cuantifica la '
    'eficiencia de la técnica de nado, detecta el inicio de la fatiga técnica e identifica las variables que la '
    'explican. La arquitectura combina una vertical de visión por computador, que estima la pose humana en dos y tres '
    'dimensiones, con una vertical de datos tabulares que segmenta el nado en ciclos de brazada, calcula indicadores '
    'cinemáticos por ciclo y modela mediante aprendizaje no supervisado el patrón técnico de referencia de cada '
    'nadador. La desviación sostenida respecto a ese patrón define el inicio de la fatiga y su atribución a cada '
    'variable se obtiene con valores de Shapley. El sistema se aplicó a 17 secuencias reales de cuatro participantes '
    'en los cuatro estilos (394 s grabados), de las que obtuvo 146 s analizables y 100 ciclos válidos. La frecuencia '
    'de ciclo estimada presenta un error relativo del 6,5 % al 8,2 % frente al conteo manual en vista lateral y '
    'frontal. Con '
    'datos sintéticos de referencia conocida, el error mediano es del 4,7 % en la frecuencia de ciclo, del 1,3 % en '
    'la velocidad y del 4,3 % en la distancia por ciclo; el inicio de la fatiga se detecta al comienzo de la '
    'transición programada, las variables con mayor atribución coinciden con las alteradas y el estilo de nado se '
    'clasifica con una exactitud del 100 % por vídeo bajo validación agrupada. Con vídeos reales, el clasificador de '
    'estilo alcanza el 45,5 % por vídeo frente al 36,4 % de la clase mayoritaria y no generaliza a participantes no '
    'vistos. En las tres sesiones reales con datos suficientes (10 a 27 ciclos) no se detecta fatiga sostenida. El '
    'análisis de sensibilidad sobre datos sintéticos muestra una tasa de detección del 100 % con un 10 % de falsas '
    'alarmas en la configuración elegida. El sistema se ejecuta en un ordenador personal sin GPU. La '
    'principal limitación es la escasez de datos reales anotados y la ausencia de una validación experimental de la '
    'fatiga en nadadores reales.')
PALABRAS_CLAVE = ('visión por computador; estimación de pose humana; aprendizaje no supervisado; detección de '
                  'anomalías; inteligencia artificial explicable; biomecánica de la natación')
ABSTRACT = (
    'Swimming technique and the onset of fatigue are usually assessed through the coach’s subjective observation or '
    'through costly instrumented systems. This work presents StrokeLab, an explainable biomechanical analysis system '
    'that, from conventional monocular video, quantifies swimming technique efficiency, detects the onset of '
    'technical fatigue and identifies the variables that explain it. The architecture combines a computer vision '
    'vertical, which estimates two- and three-dimensional human pose, with a tabular vertical that segments swimming '
    'into stroke cycles, computes per-cycle kinematic indicators and models each swimmer’s reference technique '
    'through unsupervised learning. A sustained deviation from that reference defines fatigue onset, and its '
    'attribution to each variable is obtained with Shapley values. The system was applied to 17 real sequences of four '
    'participants in the four strokes (394 s recorded), yielding 146 s of analysable video and 100 valid cycles. The '
    'estimated stroke rate shows a relative error of 6.5 % to 8.2 % against manual counts in side and front views. On '
    'synthetic data with known ground truth, the median error is 4.7 % for stroke rate, 1.3 % for velocity and 4.3 % '
    'for distance per stroke; fatigue onset is detected at the start of the programmed transition, the variables with '
    'the highest attribution match the altered ones, and swimming style is classified with 100 % per-video accuracy '
    'under grouped validation. On real videos, the style classifier reaches 45.5 % per-video accuracy against a 36.4 % '
    'majority baseline and does not generalise to unseen participants. No sustained fatigue is detected in the three '
    'real sessions with enough data (10 to 27 cycles). A sensitivity analysis on synthetic data shows a 100 % '
    'detection rate with 10 % false alarms for the chosen configuration. '
    'The system runs on a personal computer without a GPU. The main limitation is the scarcity of annotated real data '
    'and the lack of an experimental validation of fatigue in real swimmers.')
KEYWORDS = ('computer vision; human pose estimation; unsupervised learning; anomaly detection; explainable '
            'artificial intelligence; swimming biomechanics')


# ---------------------------------------------------------------- capítulo 1

def cap1_contexto(w):
    w.p('El rendimiento en natación depende de la capacidad del nadador para mantener una técnica eficiente durante '
        'toda la prueba. Con la fatiga, la técnica se degrada: aumenta la frecuencia de ciclo, disminuye la distancia '
        'recorrida en cada ciclo y cambia la coordinación de los brazos [@craig1979; @alberty2005]. En el entrenamiento '
        'habitual, estos cambios se valoran mediante observación visual, un procedimiento subjetivo que no permite '
        'determinar con precisión el instante en que comienzan ni la variable técnica que se altera en primer lugar.')
    w.p('La relación entre técnica y rendimiento tiene una base física: la resistencia hidrodinámica crece con el '
        'cuadrado de la velocidad y la potencia necesaria para vencerla, con su cubo. En consecuencia, cuando la fatiga '
        'reduce la potencia disponible, el nadador solo puede sostener la velocidad mejorando la eficiencia de su '
        'técnica. Este modelo hidrodinámico se presenta en el Capítulo 2 como conocimiento previo del dominio y no forma '
        'parte de los modelos de inteligencia artificial del sistema.')
    w.p('Los avances recientes en visión por computador, en particular la estimación de la pose humana mediante redes '
        'neuronales profundas, permiten obtener la posición de las articulaciones a partir de vídeo convencional, sin '
        'marcadores ni sensores. Este trabajo aprovecha esa capacidad para construir un sistema accesible de análisis '
        'de la técnica y de la fatiga en natación.')


def cap1_problema(w):
    w.p('No se dispone de una herramienta accesible que, a partir de un único vídeo y sin instrumentación adicional, '
        'cuantifique la **eficiencia de la técnica de nado**, realice la **detección del inicio de la fatiga técnica** '
        'y proporcione la **atribución de esa fatiga a variables biomecánicas interpretables** por el entrenador. Los '
        'sistemas comerciales requieren sensores inerciales, varias cámaras o marcadores, y entregan métricas sin '
        'explicar su relación con el estado del nadador.')
    w.p('El proyecto se plantea como un trabajo de investigación aplicada que da lugar a un producto funcional, sin '
        'colaboración con empresa. Los datos consisten en vídeos subacuáticos y de superficie de ocho nadadores de un '
        'club, registrados con una cámara GoPro y con un teléfono móvil.')


def cap1_objetivos(w):
    w.p('El objetivo general es desarrollar un sistema de inteligencia artificial explicable que, a partir de vídeo, '
        'cuantifique la eficiencia de la técnica de nado, detecte el inicio de la fatiga técnica y atribuya sus causas '
        'a variables biomecánicas mediante valores de Shapley, con ejecución en un ordenador personal sin unidad de '
        'procesamiento gráfico (GPU). Los objetivos específicos, detallados en el Capítulo 3, abarcan la selección del '
        'modelo de estimación de pose, la segmentación del nado en ciclos, la detección no supervisada de la fatiga, su '
        'explicación y la clasificación del estilo de nado.')


def cap1_resultados(w):
    w.vinetas([
        'Sistema completo de análisis, ejecutable en la CPU de un ordenador personal, para un vídeo o para un conjunto de vídeos, con pruebas automáticas.',
        'Comparativa de modelos de estimación de pose sobre vídeo subacuático real y selección justificada del modelo.',
        'Segmentación del nado en ciclos de brazada en vista lateral y frontal, con un error relativo de la frecuencia de ciclo del 6,5 %, 7,6 % y 8,2 % frente al conteo manual en tres secuencias reales.',
        'Detección del inicio de la fatiga y atribución por variable validadas con datos sintéticos de referencia conocida: errores medianos del 4,7 % (frecuencia de ciclo), 1,3 % (velocidad) y 4,3 % (distancia por ciclo).',
        'Clasificación del estilo de nado con una exactitud del 100 % por vídeo en datos sintéticos, bajo validación agrupada.',
        'Análisis biomecánico completo de un participante real (P1, crol, cinco secuencias) y ausencia de falsos positivos de fatiga en secuencias cortas.',
        'Aplicación del sistema a un conjunto real de 17 secuencias de cuatro participantes y cuatro estilos (394 s grabados, 146 s analizables, 100 ciclos válidos), con perfiles de frecuencia y técnica por participante.',
        'Evaluación del clasificador de estilo con vídeos reales (45,5 % por vídeo frente al 36,4 % de la clase mayoritaria) y cuantificación de la distancia entre el dominio sintético y el real.',
        'Análisis de sensibilidad del detector de fatiga y de robustez del conteo de ciclos frente al ruido, con datos sintéticos.',
        'Evaluación de la reconstrucción 3D frente a la 2D, con identificación de sus límites en la extremidad inferior.',
    ])


def cap1_estructura(w):
    w.p('El Capítulo 2 presenta el marco teórico: la biomecánica de la natación, los fundamentos de visión por '
        'computador y estimación de pose, las métricas de evaluación, la detección de anomalías, la clasificación '
        'supervisada y la explicabilidad, además del modelo hidrodinámico. El Capítulo 3 formula los objetivos. El '
        'Capítulo 4 describe la planificación, la solución desarrollada, los recursos, el presupuesto y los resultados. '
        'El Capítulo 5 discute las decisiones metodológicas y las limitaciones, el Capítulo 6 recoge las conclusiones y '
        'el Capítulo 7 las líneas de trabajo futuras. Los anexos incluyen la guía de ejecución, la estructura del código '
        'y las pruebas automáticas.')


# ---------------------------------------------------------------- capítulo 2

def cap2_estado(w):
    w.p('Este capítulo introduce los conceptos en los que se apoya StrokeLab. En cada apartado se presenta la teoría y '
        'el estado del arte; el Capítulo 4 describe cómo se ha adaptado cada técnica al análisis de la natación.')

    w.h3('Biomecánica del crol y eficiencia de la técnica de nado')
    w.p('El nado se describe mediante ciclos de brazada. En crol, un ciclo comprende dos brazadas, una de cada brazo. '
        'Las tres magnitudes básicas son la frecuencia de ciclo, SR (*stroke rate*, frecuencia de brazada), la distancia '
        'por ciclo, DPS (*distance per stroke*, distancia por ciclo) y la velocidad media de nado, que se relacionan '
        'según la Ecuación {eq:vel} [@craig1979].')
    w.ecuacion('vel', ['v', '=', ('frac', ['SR', '·', 'DPS'], '60')],
               'Velocidad media de nado a partir de la frecuencia y la distancia por ciclo',
               [('*v*', 'velocidad media de nado (m/s)'),
                ('SR', 'frecuencia de ciclo (*stroke rate*), en ciclos por minuto (ciclos/min); el factor 60 la convierte a ciclos por segundo'),
                ('DPS', 'distancia recorrida en un ciclo (*distance per stroke*), en metros (m)')])
    w.p('Para una misma velocidad, los nadadores más eficientes emplean una frecuencia menor y una distancia por ciclo '
        'mayor. Costill et al. [@costill1985] propusieron el índice de brazada, SI (*stroke index*, índice de brazada), '
        'como indicador de la economía del nado (Ecuación {eq:si}).')
    w.ecuacion('si', ['SI', '=', 'v', '·', 'DPS'], 'Índice de brazada (stroke index)',
               [('SI', 'índice de brazada (m²/s); valores mayores indican una técnica más económica'),
                ('*v*', 'velocidad media (m/s)'), ('DPS', 'distancia por ciclo (m)')])
    w.p('Otros factores asociados a la eficiencia propulsiva son la flexión del codo durante el agarre (*catch*, fase '
        'en que la mano empieza a empujar el agua), la amplitud de la brazada, la simetría entre ambos brazos y la '
        'alineación horizontal del cuerpo, que reduce el área frontal y, con ella, la resistencia [@toussaint1992; '
        '@chollet2000].')

    w.h3('La fatiga en natación')
    w.p('La fatiga técnica se manifiesta como un cambio progresivo del patrón de nado: disminuye la distancia por ciclo, '
        'que a menudo se compensa con un aumento de la frecuencia, y se alteran la coordinación entre brazos y la '
        'variación de la velocidad dentro del ciclo [@alberty2005]. Estos cambios son individuales: cada nadador se fatiga '
        'de manera distinta. Por ello, una referencia poblacional resulta menos informativa que la comparación del '
        'nadador con su propio estado de partida, enfoque que adopta este trabajo.')

    w.h3('Visión por computador y aprendizaje profundo')
    w.p('La visión por computador es la disciplina que extrae información de imágenes y vídeos de forma automática. '
        'Una imagen digital se representa como un tensor de dimensiones alto × ancho × canales, cuyos valores son las '
        'intensidades de cada píxel. Desde 2012, el campo está dominado por el aprendizaje profundo (*deep learning*), '
        'en el que una red neuronal con muchas capas aprende directamente de los datos las representaciones necesarias '
        'para la tarea [@lecun2015].')
    w.p('La arquitectura de referencia es la red neuronal convolucional, CNN (*convolutional neural network*). Cada '
        'capa convolucional aplica filtros pequeños que se desplazan por la imagen y producen mapas de características '
        '(*feature maps*): las primeras capas responden a bordes y texturas, y las más profundas a partes del cuerpo o '
        'a objetos completos. Las funciones de activación no lineales y las capas de reducción de resolución permiten '
        'combinar información local en descriptores cada vez más globales. Más recientemente, los *transformers*, '
        'basados en mecanismos de atención que relacionan todas las partes de la entrada entre sí [@vaswani2017], se '
        'han trasladado a la visión con resultados de referencia.')
    w.p('El entrenamiento de estas redes requiere grandes conjuntos de imágenes anotadas. Cuando los datos de la tarea '
        'son escasos, se recurre al aprendizaje por transferencia (*transfer learning*): se parte de un modelo ya '
        'entrenado en un conjunto amplio y genérico y se reutiliza, directamente o con un ajuste fino (*fine-tuning*), '
        'en el problema concreto [@pan2010]. Esta es la estrategia adoptada en StrokeLab.')

    w.h3('Estimación de la pose humana')
    w.p('La estimación de la pose humana consiste en localizar en la imagen un conjunto predefinido de puntos '
        'anatómicos (*keypoints*, puntos clave), como hombros, codos, muñecas, caderas, rodillas y tobillos. El formato '
        'más extendido es el del conjunto COCO (*Common Objects in Context*), con 17 puntos por persona [@lin2014]. '
        'Existen dos paradigmas principales:')
    w.vinetas([
        '**Descendente** (*top-down*): primero se detecta cada persona con un detector de objetos y después se estiman sus puntos dentro del recuadro. Es más preciso, pero su coste crece con el número de personas.',
        '**Ascendente** (*bottom-up*): se detectan todos los puntos de la imagen y después se agrupan por persona, como en OpenPose, que emplea campos de afinidad entre partes [@cao2017].',
    ])
    w.p('En cuanto a la salida de la red, los métodos basados en mapas de calor (*heatmaps*) predicen para cada '
        'articulación una imagen de probabilidad cuyo máximo indica su posición, como HRNet, que mantiene '
        'representaciones de alta resolución en toda la red [@sun2019]. Los métodos de regresión predicen '
        'directamente las coordenadas. La familia YOLO (*You Only Look Once*) resuelve la detección de objetos en una '
        'única pasada de la red [@redmon2016]; YOLO-Pose extiende esta idea y predice, en la misma pasada, el recuadro '
        'de cada persona y sus puntos, con una función de pérdida basada en la similitud de puntos clave [@maji2022]. '
        'Ultralytics distribuye versiones de distintos tamaños (*nano*, *small*, *medium*) preentrenadas en COCO '
        '[@jocher2023].')
    w.p('Para dispositivos con recursos limitados se han desarrollado modelos ligeros de una sola persona: MoveNet, con '
        'una red MobileNetV2 y entrada de 192 × 192 píxeles en su versión *Lightning* [@google2021], y BlazePose, que '
        'estima 33 puntos [@bazarevsky2020]. En el extremo opuesto, ViTPose emplea un *transformer* de visión y alcanza '
        'los mejores resultados en COCO a costa de un elevado coste computacional [@xu2022]. La Tabla {tab:modelos} '
        'resume los modelos considerados.')
    w.tabla([
        ['Modelo', 'Paradigma', 'Arquitectura', 'AP en COCO', 'Papel en este trabajo'],
        ['OpenPose [@cao2017]', 'Ascendente', 'CNN y campos de afinidad', '61,8 (test-dev)', 'Referencia histórica'],
        ['HRNet-W48 [@sun2019]', 'Descendente', 'CNN de alta resolución', '75,5 (test-dev)', 'No usado (coste en CPU)'],
        ['YOLOv8n-Pose [@jocher2023]', 'Una etapa', 'CNN detector y puntos', '50,4 (val)', 'Modelo elegido'],
        ['YOLO11n-Pose [@jocher2023]', 'Una etapa', 'CNN detector y puntos', '50,0 (val)', 'Comparado'],
        ['YOLOv8s-Pose [@jocher2023]', 'Una etapa', 'CNN detector y puntos', '60,0 (val)', 'Comparado'],
        ['MoveNet Lightning [@google2021]', 'Una persona', 'MobileNetV2', 'Sin AP comparable publicada', 'Comparado; opción'],
        ['BlazePose [@bazarevsky2020]', 'Una persona', 'CNN ligera, 33 puntos', 'Evaluado con PCK propio', 'Opción'],
        ['ViTPose-G [@xu2022]', 'Descendente', 'Transformer de visión', '80,9 (test-dev)', 'Trabajo futuro'],
    ], 'Modelos de estimación de pose considerados. AP: precisión media en COCO según las publicaciones originales.',
        clave='modelos', anchos=[3.8, 2.4, 3.4, 2.8, 3.6], size=8)
    w.p('La estimación de pose en natación presenta dificultades específicas: refracción, burbujas, iluminación '
        'variable, oclusión parcial del cuerpo por la superficie del agua y escasez de imágenes anotadas [@einfalt2018]. '
        'El conjunto sintético SwimXYZ ofrece secuencias generadas por ordenador de los cuatro estilos para entrenar y '
        'evaluar modelos en este dominio [@fiche2023].')

    w.h3('Métricas de evaluación de la estimación de pose')
    w.p('La precisión de un modelo de pose se mide comparando los puntos estimados con anotaciones manuales de '
        'referencia (*ground truth*). La métrica oficial de COCO es la similitud de puntos clave, OKS (*Object Keypoint '
        'Similarity*), que desempeña el papel de la intersección sobre la unión en la detección de objetos [@lin2014] '
        '(Ecuación {eq:oks}).')
    w.ecuacion('oks', ['OKS', '=', ('frac',
                       ('sum', 'i', None, ['exp', ('par', ['−', ('frac', ('sup', ('sub', 'd', 'i'), '2'),
                                                                     ['2', ('sup', 's', '2'), ('sup', ('sub', 'k', 'i'), '2')])]),
                                          'δ', ('par', [('sub', 'v', 'i'), '>', '0'])]),
                       ('sum', 'i', None, ['δ', ('par', [('sub', 'v', 'i'), '>', '0'])]))],
               'Similitud de puntos clave (OKS)',
               [('*d*_{i}', 'distancia euclídea entre el punto estimado y el anotado de la articulación *i* (píxeles)'),
                ('*s*', 'escala del objeto, raíz cuadrada del área de la persona (píxeles)'),
                ('*k*_{i}', 'constante de tolerancia propia de cada articulación (adimensional)'),
                ('*v*_{i}', 'indicador de visibilidad de la articulación en la anotación; δ(·) vale 1 si se cumple la condición y 0 en otro caso'),
                ('OKS', 'similitud entre 0 (sin coincidencia) y 1 (coincidencia perfecta)')])
    w.p('Otra métrica habitual es el porcentaje de puntos correctos, PCK (*Percentage of Correct Keypoints*), que '
        'cuenta los puntos situados a menos de una fracción α de una longitud de referencia, como el tronco o la cabeza '
        '(PCKh) [@andriluka2014] (Ecuación {eq:pck}).')
    w.ecuacion('pck', [('sub', 'PCK', 'α'), '=', ('frac', '1', 'N'),
                       ('sum', ['i', '=', '1'], 'N', ['𝟙', ('par', [('norm', [('acc', ('sub', 'p', 'i'), '̂'), '−', ('sub', 'p', 'i')]), '≤',
                                                                 'α', '·', ('sub', 'd', 'ref')])])],
               'Porcentaje de puntos correctos (PCK)',
               [('*N*', 'número total de puntos evaluados'),
                ('*p̂*_{i}, *p*_{i}', 'posición estimada y posición de referencia del punto *i* (píxeles)'),
                ('*d*_{ref}', 'longitud de referencia del cuerpo, por ejemplo el tronco (píxeles)'),
                ('α', 'umbral relativo de tolerancia (habitualmente 0,2 o 0,5); 𝟙(·) vale 1 si la condición se cumple'),
                ('PCK_{α}', 'proporción de puntos correctos, entre 0 y 1')])
    w.p('A partir de la OKS se calcula la precisión media, AP (*Average Precision*): para un umbral de OKS se '
        'consideran correctas las detecciones que lo superan y se integra la curva de precisión frente a exhaustividad. '
        'COCO promedia la AP sobre diez umbrales de OKS entre 0,50 y 0,95, valor que se denomina mAP (*mean Average '
        'Precision*) (Ecuación {eq:ap}).')
    w.ecuacion('ap', [('sub', 'AP', 't'), '=', ('int', '0', '1', [('sub', 'P', 't'), ('par', 'R'), 'dR']), ',     ',
                      'mAP', '=', ('frac', '1', ('bar', 'T')), ('sum', ['t', '∈', 'T'], None, ('sub', 'AP', 't'))],
               'Precisión media (AP) y su promedio sobre umbrales de OKS (mAP)',
               [('*P*_{t}(*R*)', 'precisión en función de la exhaustividad *R* cuando una detección se considera correcta si su OKS ≥ *t*'),
                ('*T*', 'conjunto de umbrales de OKS {0,50; 0,55; …; 0,95}; |*T*| = 10'),
                ('AP, mAP', 'valores entre 0 y 1, que suelen expresarse en porcentaje')])
    w.p('Todas estas métricas requieren un conjunto de imágenes con las articulaciones anotadas manualmente. Su '
        'aplicabilidad a los datos de este trabajo se discute en el Capítulo 4.')

    w.h3('Elevación de la pose a tres dimensiones')
    w.p('La estimación 3D a partir de una sola cámara es un problema mal planteado, porque infinitas posturas 3D '
        'producen la misma proyección. La estrategia más extendida es la elevación (*lifting*): un modelo recibe la '
        'secuencia de puntos 2D y predice su profundidad, aprovechando las regularidades del cuerpo humano aprendidas '
        'de grandes conjuntos con captura de movimiento [@martinez2017]. El conjunto de referencia es Human3.6M, con '
        'actores en un laboratorio realizando acciones cotidianas de pie [@ionescu2014]. MotionBERT emplea un '
        '*transformer* con atención espacial y temporal alternada (DSTformer) preentrenado para recuperar movimiento '
        'a partir de entradas 2D ruidosas [@zhu2023]. Al haberse entrenado con personas de pie en tierra, su '
        'transferencia a un nadador horizontal bajo el agua no está garantizada, aspecto que se evalúa en este trabajo.')

    w.h3('Detección de anomalías y aprendizaje no supervisado')
    w.p('El aprendizaje no supervisado busca estructura en datos sin etiquetas. Una de sus tareas es la detección de '
        'anomalías, que identifica observaciones que se apartan del comportamiento normal [@chandola2009]. Es el '
        'planteamiento adecuado para la fatiga, ya que no se dispone de etiquetas que indiquen en qué ciclo está '
        'fatigado un nadador, pero sí de un periodo inicial en el que se le puede suponer descansado.')
    w.p('*Isolation Forest* (bosque de aislamiento) [@liu2008] parte de una idea sencilla: las observaciones anómalas '
        'son escasas y distintas, por lo que se aíslan con menos particiones aleatorias que las normales. El algoritmo '
        'construye un conjunto de árboles de aislamiento; en cada nodo elige al azar una variable y un valor de corte '
        'entre su mínimo y su máximo, y divide los datos hasta aislar cada observación. La longitud del camino *h*(*x*) '
        'desde la raíz hasta la hoja de una observación es corta si esta es anómala. La puntuación de anomalía se '
        'normaliza según la Ecuación {eq:ifscore}.')
    w.ecuacion('ifscore', ['s', ('par', ['x', ',', 'n']), '=', ('sup', '2', ['−', ('frac', ['E', ('cor', ['h', ('par', 'x')])],
                                                                                     ['c', ('par', 'n')])])],
               'Puntuación de anomalía de Isolation Forest',
               [('*s*(*x*, *n*)', 'puntuación de anomalía de la observación *x*, entre 0 y 1; valores próximos a 1 indican anomalía y valores inferiores a 0,5, normalidad'),
                ('*E*[*h*(*x*)]', 'longitud media del camino de *x* en el conjunto de árboles (número de particiones)'),
                ('*c*(*n*)', 'longitud media esperada del camino en un árbol construido con *n* observaciones (Ecuación {eq:ifc})')])
    w.ecuacion('ifc', ['c', ('par', 'n'), '=', '2', 'H', ('par', ['n', '−', '1']), '−', ('frac', ['2', ('par', ['n', '−', '1'])], 'n'),
                       ',     ', 'H', ('par', 'i'), '≈', 'ln', ('par', 'i'), '+', 'γ'],
               'Factor de normalización de Isolation Forest',
               [('*n*', 'número de observaciones con que se construye cada árbol'),
                ('*H*(*i*)', 'número armónico, aproximado mediante el logaritmo neperiano'),
                ('γ', 'constante de Euler-Mascheroni (≈ 0,5772)')])
    w.p('El algoritmo tiene coste lineal, no necesita suponer una distribución de los datos y puede entrenarse solo '
        'con observaciones normales, propiedades que justifican su elección.')

    w.h3('Detección de puntos de cambio')
    w.p('La detección de puntos de cambio (*change point detection*) localiza los instantes en que cambian las '
        'propiedades estadísticas de una serie temporal. El algoritmo PELT (*Pruned Exact Linear Time*) encuentra de '
        'forma exacta la segmentación que minimiza el coste de la Ecuación {eq:pelt} con un coste computacional lineal, '
        'gracias a una regla de poda de candidatos [@killick2012].')
    w.ecuacion('pelt', [('sub', 'mín', ['m', ',', 'τ']), ('sum', ['i', '=', '1'], ['m', '+', '1'],
                        ['C', ('par', ('sub', 'y', [('sub', 'τ', ['i', '−', '1']), '+', '1', ':', ('sub', 'τ', 'i')]))]),
                        '+', 'β', 'm', ',     ', 'C', ('par', 'y'), '=', ('sum', 't', None, ('sup', ('par', [('sub', 'y', 't'), '−', ('media', 'y')]), '2'))],
               'Función objetivo de PELT con coste cuadrático',
               [('*m*', 'número de puntos de cambio; τ_{1}, …, τ_{m} son sus posiciones en la serie'),
                ('*C*(·)', 'coste de un segmento; con coste cuadrático (L2) es la suma de desviaciones cuadráticas respecto a su media *ȳ*'),
                ('β', 'penalización por cada punto de cambio adicional; en este trabajo β = 2 ln *n*, con *n* la longitud de la serie')])

    w.h3('Clasificación supervisada con conjuntos de árboles')
    w.p('En el aprendizaje supervisado, el modelo aprende la relación entre unas variables de entrada y una etiqueta '
        'conocida. Un árbol de decisión divide recursivamente el espacio de las variables con preguntas del tipo '
        '«¿variable *j* ≤ umbral?», eligiendo en cada nodo la división que más reduce la impureza de las clases, medida '
        'habitualmente con el índice de Gini (Ecuación {eq:gini}).')
    w.ecuacion('gini', ['G', '=', '1', '−', ('sum', ['k', '=', '1'], 'K', ('sup', ('sub', 'p', 'k'), '2'))],
               'Índice de impureza de Gini de un nodo',
               [('*K*', 'número de clases (en este trabajo, cuatro estilos de nado)'),
                ('*p*_{k}', 'proporción de observaciones de la clase *k* en el nodo; *G* = 0 indica un nodo puro')])
    w.p('Un árbol aislado se ajusta en exceso a los datos de entrenamiento. El bosque aleatorio (*Random Forest*) '
        'combina muchos árboles entrenados sobre muestras con reemplazo de los datos (*bagging*) y con un subconjunto '
        'aleatorio de variables en cada división, y decide por votación; así reduce la varianza sin aumentar el sesgo '
        '[@breiman2001]. Los métodos de *boosting*, como XGBoost, construyen los árboles de forma secuencial para '
        'corregir los errores de los anteriores [@chen2016].')
    w.p('La evaluación de un clasificador debe estimar su rendimiento con datos no vistos. La validación cruzada '
        'divide los datos en *k* particiones y entrena y evalúa *k* veces. Cuando las observaciones están agrupadas '
        '(por ejemplo, muchos fotogramas o ventanas de un mismo vídeo), la partición aleatoria provoca fuga de datos '
        '(*data leakage*): observaciones casi idénticas acaban en entrenamiento y en prueba, y el rendimiento se '
        'sobreestima [@kaufman2012]. La validación cruzada agrupada (*GroupKFold*) asigna cada grupo completo a una '
        'única partición y evita este problema.')

    w.h3('Inteligencia artificial explicable')
    w.p('La inteligencia artificial explicable, XAI (*explainable artificial intelligence*), reúne métodos que '
        'permiten entender por qué un modelo produce una salida. Los valores de Shapley, procedentes de la teoría de '
        'juegos cooperativos [@shapley1953], reparten el resultado de una coalición entre sus jugadores de forma justa. '
        'Aplicados a un modelo, los jugadores son las variables de entrada y el resultado es la predicción (Ecuación '
        '{eq:shapley}).')
    w.ecuacion('shapley', [('sub', 'φ', 'j'), '=', ('sum', ['S', '⊆', 'F', '∖', ('llave', 'j')], None,
                           [('frac', [('bar', 'S'), '!', ('par', [('bar', 'F'), '−', ('bar', 'S'), '−', '1']), '!'], [('bar', 'F'), '!']),
                            ('cor', [('sub', 'f', 'x'), ('par', ['S', '∪', ('llave', 'j')]), '−', ('sub', 'f', 'x'), ('par', 'S')])])],
               'Valor de Shapley de la variable j',
               [('φ_{j}', 'contribución de la variable *j* a la predicción para la observación *x* (en unidades de la salida del modelo)'),
                ('*F*', 'conjunto de todas las variables; *S* es un subconjunto que no contiene *j*'),
                ('*f*_{x}(*S*)', 'predicción del modelo para *x* cuando solo se conocen las variables de *S*')])
    w.p('SHAP (*SHapley Additive exPlanations*) [@lundberg2017] expresa cada predicción como la suma de un valor base '
        'y de las contribuciones de cada variable (Ecuación {eq:shapadd}), lo que permite explicaciones locales (una '
        'observación) y globales (todo el conjunto). Para modelos basados en árboles, TreeSHAP calcula los valores '
        'exactos en tiempo polinómico [@lundberg2020], lo que lo hace aplicable tanto a Isolation Forest como al bosque '
        'aleatorio.')
    w.ecuacion('shapadd', ['f', ('par', 'x'), '=', ('sub', 'φ', '0'), '+', ('sum', ['j', '=', '1'], 'M', ('sub', 'φ', 'j'))],
               'Descomposición aditiva de SHAP',
               [('*f*(*x*)', 'salida del modelo para la observación *x*'),
                ('φ_{0}', 'valor base: salida media del modelo en los datos de referencia'),
                ('*M*', 'número de variables de entrada')])

    w.h3('Procesado de señales temporales')
    w.p('Las coordenadas de las articulaciones a lo largo del tiempo forman señales ruidosas. El filtro de '
        'Savitzky-Golay ajusta por mínimos cuadrados un polinomio de grado bajo en una ventana deslizante y conserva '
        'mejor los máximos y mínimos que una media móvil [@savitzky1964]. El análisis de componentes principales, PCA '
        '(*principal component analysis*), obtiene las direcciones de máxima varianza de un conjunto de datos; la '
        'primera componente es la dirección en la que los datos se mueven más [@jolliffe2016]. Ambas técnicas se emplean '
        'en la segmentación del nado en ciclos.')


def cap2_contexto(w):
    w.p('El modelo hidrodinámico constituye conocimiento previo del dominio y no un componente de inteligencia '
        'artificial. Explica por qué la eficiencia técnica es determinante. La fuerza de arrastre que se opone al '
        'avance del nadador viene dada por la Ecuación {eq:arrastre}.')
    w.ecuacion('arrastre', [('sub', 'F', 'D'), '=', ('frac', '1', '2'), 'ρ', ('sub', 'C', 'D'), 'A', ('sup', 'v', '2')],
               'Fuerza de arrastre hidrodinámico',
               [('*F*_{D}', 'fuerza de arrastre (N)'), ('ρ', 'densidad del agua (≈ 1000 kg/m³)'),
                ('*C*_{D}', 'coeficiente de arrastre, adimensional, que depende de la forma y la posición del cuerpo'),
                ('*A*', 'área frontal proyectada del nadador (m²)'), ('*v*', 'velocidad de nado (m/s)')])
    w.p('La potencia necesaria para vencer el arrastre es el producto de la fuerza por la velocidad (Ecuación '
        '{eq:potencia}).')
    w.ecuacion('potencia', ['P', '=', ('sub', 'F', 'D'), 'v', '=', ('frac', '1', '2'), 'ρ', ('sub', 'C', 'D'), 'A', ('sup', 'v', '3')],
               'Potencia necesaria para vencer el arrastre',
               [('*P*', 'potencia mecánica (W)'), ('restantes símbolos', 'como en la Ecuación {eq:arrastre}')])
    w.p('Por la dependencia cúbica, nadar un 10 % más rápido exige un 33 % más de potencia (1,1³ ≈ 1,33). Cuando la '
        'fatiga reduce la potencia disponible, el nadador solo mantiene la velocidad si reduce *C*_{D} o *A*, es decir, '
        'si mejora su técnica [@toussaint1992]. Como *C*_{D} y *A* varían entre nadadores y no pueden medirse con '
        'fiabilidad desde un vídeo 2D, la potencia no se emplea como variable de los modelos: se usan indicadores '
        'cinemáticos directamente medibles, interpretados a la luz de esta relación.')
    w.p('La revisión del estado del arte muestra que los trabajos existentes miden la técnica o detectan la fatiga, '
        'pero no combinan, en un sistema de bajo coste que funcione en un ordenador personal, una detección no '
        'supervisada del inicio de la fatiga con una atribución por variable interpretable por el entrenador. Esa es la '
        'aportación de StrokeLab.')


def cap2_problema(w):
    w.p('El problema se concreta en tres preguntas de investigación: (1) cómo obtener la pose de un nadador bajo el '
        'agua con un modelo que funcione en CPU; (2) cómo transformar esa pose en ciclos de brazada y variables con '
        'significado biomecánico; y (3) cómo determinar, sin etiquetas de fatiga, el ciclo en que la técnica se degrada '
        'y qué variables explican ese cambio. La tercera es la central y se aborda mediante detección de anomalías '
        'respecto al estado inicial del propio nadador y explicación con valores de Shapley.')


# ---------------------------------------------------------------- capítulo 3

def cap3_generales(w):
    w.p('El objetivo general del presente trabajo es desarrollar un sistema de inteligencia artificial explicable '
        'que, a partir de un vídeo de nado y en un ordenador personal sin GPU, cuantifique la eficiencia de la técnica '
        'de nado, detecte el inicio de la fatiga técnica y atribuya sus causas a variables biomecánicas interpretables.')


def cap3_especificos(w):
    w.vinetas([
        'OE1. Comparar modelos de estimación de pose (YOLO en varios tamaños, MoveNet y MediaPipe) sobre vídeo subacuático real y en CPU, y seleccionar el más adecuado de forma justificada.',
        'OE2. Elevar la pose a 3D para vistas frontales y oblicuas, y evaluar la reconstrucción 3D frente a la 2D.',
        'OE3. Segmentar automáticamente el nado en ciclos de brazada y validar la frecuencia de ciclo frente a un conteo manual.',
        'OE4. Calcular por ciclo indicadores de eficiencia y medidas articulares de codos, hombros, caderas, rodillas y pies.',
        'OE5. Detectar el inicio de la fatiga como desviación sostenida respecto al patrón técnico inicial del propio nadador.',
        'OE6. Atribuir cada detección a variables biomecánicas mediante valores de Shapley y expresarla en un texto comprensible para el entrenador.',
        'OE7. Clasificar el estilo de nado con validación agrupada por vídeo.',
        'OE8. Generar un vídeo anotado que muestre el estado de fatiga a lo largo del nado.',
        'OE9. Evaluar el sistema con datos sintéticos de referencia conocida ante la ausencia de datos reales etiquetados.',
    ])


def cap3_beneficios(w):
    w.p('El entrenador obtiene, con una cámara ya disponible, una medida objetiva de cuándo y cómo se degrada la '
        'técnica de cada nadador y de qué aspecto conviene trabajar. La ejecución local evita depender de servicios de '
        'pago y de transferir los vídeos fuera del club. En el plano académico, el trabajo muestra cómo aplicar la '
        'detección de anomalías explicable a un problema deportivo sin etiquetas y cómo validar un sistema de visión '
        'por computador cuando los datos anotados son escasos.')


# ---------------------------------------------------------------- capítulo 4

def cap4_planificacion(w):
    w.p('El proyecto se ha desarrollado en cinco fases entre mayo y octubre de 2026: planteamiento, primer prototipo, '
        'revisión por parte del director, rediseño y validación, y redacción de la memoria. La revisión del 1 de '
        'septiembre marcó un punto de inflexión: se reorganizó el sistema en dos verticales, la explicabilidad pasó a ser '
        'el eje del producto y el modelo hidrodinámico se trasladó al marco teórico. La Figura {fig:gantt} muestra la '
        'distribución temporal de las tareas.')
    w.figura(FIG / 'gantt.png', 'Planificación temporal del proyecto (diagrama de Gantt).', clave='gantt')


def cap4_solucion(w):
    w.h3('Arquitectura y modos de funcionamiento')
    w.p('StrokeLab se organiza en dos verticales de inteligencia artificial conectadas por un formato intermedio común: '
        'una secuencia de 17 puntos articulares por fotograma (Figura {fig:arq}). La vertical de visión transforma el '
        'vídeo en puntos 2D y 3D; la vertical tabular transforma los puntos en ciclos, variables, eficiencia, inicio de '
        'la fatiga y su atribución.')
    w.figura(FIG / 'arquitectura.png', 'Arquitectura de StrokeLab: vertical de visión y vertical tabular.', clave='arq')
    w.p('El sistema admite tres modos de entrada. El modo **vídeo** recorre las dos verticales. El modo **tabular** '
        'recibe variables por ciclo ya calculadas y entra directamente en la vertical tabular. El modo **audio** '
        '(sonido de las brazadas y de la respiración) se plantea como trabajo futuro. Todo el proceso se ejecuta en '
        'local con un único programa (`analizar.py`) o, para un conjunto de vídeos, con `lote.py`.')

    w.h3('Uso de modelos preentrenados frente a un modelo propio')
    w.p('No se ha entrenado un modelo de estimación de pose propio por tres razones. En primer lugar, por los datos: '
        'entrenar desde cero una red de pose requiere decenas de miles de imágenes con las articulaciones anotadas; COCO '
        'contiene más de 200 000 imágenes y 250 000 personas anotadas [@lin2014], mientras que en este trabajo no se '
        'dispone de ningún fotograma subacuático anotado. En segundo lugar, por la capacidad de cómputo: el sistema debe '
        'funcionar en un ordenador personal sin GPU, donde el entrenamiento de una red profunda no es viable en el plazo '
        'del proyecto. En tercer lugar, por el estado del arte: los modelos preentrenados ya capturan la estructura del '
        'cuerpo humano y el aprendizaje por transferencia permite reutilizar ese conocimiento [@pan2010].')
    w.p('La contribución del trabajo no reside en el detector, sino en lo que se construye sobre él: la adaptación a '
        'la natación (filtros anatómicos, normalización de la pose para el 3D, señales de brazada por vista) y la '
        'vertical tabular explicable. El ajuste fino con imágenes de natación, sintéticas o propias, se plantea como '
        'línea futura (Capítulo 7).')

    w.h3('Vertical de visión: selección del modelo de pose')
    w.p('Las métricas estándar de estimación de pose (OKS, PCK y mAP, Ecuaciones {eq:oks} a {eq:ap}) exigen anotaciones '
        'manuales de las articulaciones, de las que no se dispone para vídeo subacuático. Anotar un conjunto '
        'representativo de fotogramas 5K, con articulaciones ocultas por el propio cuerpo o por la superficie, excede el '
        'alcance del proyecto. Por ello, la comparación se ha realizado con métricas operativas medibles sin anotación y '
        'se ha complementado con dos tipos de evidencia:')
    w.vinetas([
        '**Rendimiento de referencia publicado** en COCO para cada modelo (Tabla {tab:modelos}), que indica su precisión en condiciones estándar.',
        '**Validación orientada a la tarea**: el error de la frecuencia de ciclo frente al conteo manual (Tabla {tab:validacion}), que mide de forma indirecta si la calidad de la pose es suficiente para el análisis.',
    ])
    w.p('Las métricas operativas, calculadas sobre 15 tramos de 10 fotogramas repartidos por el vídeo, son: '
        'fotogramas procesados por segundo en CPU (FPS); tasa de detección, definida como el porcentaje de fotogramas '
        'con al menos cinco articulaciones de confianza superior a 0,30; confianza media de las articulaciones '
        'detectadas; y una puntuación combinada igual al producto de la tasa de detección y la confianza. MoveNet se '
        'eligió inicialmente por su fluidez en CPU, pero sobre vídeo subacuático YOLO detectó al nadador con '
        'aproximadamente el doble de confianza (0,73-0,77 frente a 0,34-0,37) y produjo 15 ciclos válidos frente a 3. '
        'Como el vídeo anotado se genera tras el análisis, la ventaja de fluidez de MoveNet dejó de ser determinante. '
        'Se eligió la variante más ligera que no pierde capacidad de detección, YOLOv8n-Pose (Tabla {tab:cpu}); '
        'ViTPose se descartó por su coste computacional en CPU.')
    w.tabla([
        ['Modelo', 'Parámetros (M)', 'FPS en CPU', 'Detección (%)', 'Confianza', 'Puntuación'],
        ['**YOLOv8n-Pose (elegido)**', '3,3', '6,6', '35,6', '0,76', '0,27'],
        ['YOLO11n-Pose', '2,9', '6,2', '37,6', '0,78', '0,29'],
        ['YOLOv8s-Pose', '11,6', '3,3', '35,6', '0,74', '0,27'],
        ['MoveNet Lightning', '—', 'No medido', '35-48 (GPU)', '0,34-0,37 (GPU)', '—'],
        ['MediaPipe Pose', '—', 'No medido', '—', '—', '—'],
    ], 'Comparativa en la CPU del ordenador personal (4 hilos) sobre la secuencia GX011614 (5120 × 2880 píxeles). La '
       'detección ronda el 36 % porque el nadador solo está en el encuadre durante parte del vídeo.',
        clave='cpu', anchos=[4.5, 2.3, 2.2, 2.4, 2.2, 2.4])
    w.p('YOLOv8n-Pose procesa uno de cada dos fotogramas, reducidos a 1920 píxeles en su lado mayor; las coordenadas '
        'se devuelven en píxeles del vídeo original. Como el modelo se entrenó con personas de pie, el sistema prueba '
        'el fotograma sin girar y girado ±90° y conserva la orientación que mejor detecta; en las secuencias del '
        'participante P1 la mejor fue la original.')

    w.h3('Vertical de visión: limpieza y filtros anatómicos')
    w.vinetas([
        'Se descartan los puntos con confianza inferior a 0,30, se interpolan los huecos de hasta 0,4 s y cada tramo se suaviza con un filtro de Savitzky-Golay de ventana ≈ 0,2 s y grado 2 [@savitzky1964].',
        '**Plausibilidad anatómica.** Bajo el agua, el modelo sitúa a veces la cadera casi sobre el hombro. Se descartan los fotogramas cuyo tronco mide fuera de [0,5; 2] veces su mediana, los segmentos de brazo o pierna de longitud imposible y los codos con ángulo inferior a 25°. En vista frontal sin 3D, la escala del cuerpo es el ancho de hombros, porque el tronco aparece acortado por la perspectiva.',
        '**Tronco girado.** El modelo dibuja en ocasiones un esqueleto vertical bajo la cabeza de un nadador horizontal. Se descartan los fotogramas cuyo tronco se desvía más de 45° de la orientación habitual, calculada como mediana axial. En la secuencia GX011614 se eliminó el 11,5 % de los fotogramas y la inclinación media del tronco pasó de 42° a 9°.',
    ])

    w.h3('Vertical de visión: elevación a 3D')
    w.p('La pose 2D se eleva a 3D con MotionBERT-Lite en CPU (≈ 25 s por vídeo). Como el modelo se entrenó con '
        'personas de pie [@ionescu2014; @zhu2023], cada fotograma se centra en la pelvis, se gira hasta dejar el tronco '
        'vertical y se normaliza por el tamaño del cuerpo; los ángulos articulares son invariantes a ese giro. El 3D se '
        'mantiene porque parte de los vídeos se registró de frente o en diagonal, donde las medidas 2D se deforman por '
        'la perspectiva. Su evaluación se presenta en la Sección 4.6.')

    w.h3('Vertical tabular: ángulos articulares')
    w.p('Los ángulos articulares se calculan a partir de tres puntos consecutivos de la cadena cinemática (Ecuación '
        '{eq:angulo}): por ejemplo, el codo con hombro, codo y muñeca.')
    w.ecuacion('angulo', ['θ', '=', 'arccos', ('par', ('frac', [('par', ['a', '−', 'b']), '·', ('par', ['c', '−', 'b'])],
                                                   [('norm', ['a', '−', 'b']), ('norm', ['c', '−', 'b'])]))],
               'Ángulo articular en el punto b',
               [('θ', 'ángulo de la articulación (grados, °); 180° corresponde al segmento completamente extendido'),
                ('*a*, *b*, *c*', 'posiciones 2D o 3D de tres articulaciones consecutivas, con *b* la articulación medida (píxeles o unidades del modelo 3D)')])
    w.p('Los valores mínimos y máximos de cada ciclo se toman como percentiles 10 y 90: con el mínimo absoluto, un único '
        'fotograma mal detectado fijaba el valor del ciclo (en GX011614 daba flexiones de rodilla de 12°).')

    w.h3('Vertical tabular: segmentación en ciclos de brazada')
    w.p('El análisis se realiza por ciclo de brazada y no por fotograma: cada observación tiene significado biomecánico '
        'y se reduce la fuerte correlación entre fotogramas consecutivos. En **vista lateral**, la señal para contar '
        'brazadas es la profundidad de la mano más profunda respecto al eje del cuerpo (Ecuación {eq:profundidad}).')
    w.ecuacion('profundidad', ['p', ('par', 't'), '=', ('sub', 'máx', ['j', '∈', ('llave', 'I, D')]),
                               ('frac', [('par', [('sub', 'w', 'j'), ('par', 't'), '−', 'h', ('par', 't')]), '·', 'n', ('par', 't')],
                                ['L', ('par', 't')])],
               'Señal de profundidad de la mano en vista lateral',
               [('*p*(*t*)', 'profundidad de la mano en el instante *t*, en longitudes de tronco (adimensional)'),
                ('*w*_{j}(*t*)', 'posición 2D de la muñeca izquierda (I) o derecha (D) (píxeles)'),
                ('*h*(*t*)', 'punto medio de los hombros (píxeles)'),
                ('*n*(*t*)', 'vector unitario perpendicular al eje del tronco orientado hacia el fondo de la piscina'),
                ('*L*(*t*)', 'longitud del tronco, distancia entre el punto medio de los hombros y el de las caderas (píxeles)')])
    w.p('En cada brazada la mano desciende por debajo del cuerpo durante la tracción y vuelve a subir, de modo que cada '
        'máximo de *p*(*t*) corresponde a una brazada (Figura {fig:brazadas}). Se toma la mano más profunda de las dos '
        'porque, en vista lateral, el modelo de pose asigna casi las mismas coordenadas a ambas muñecas: copia el brazo '
        'visible en el que queda oculto por el cuerpo. El ritmo típico es la mediana de los intervalos entre brazadas '
        'consecutivas dentro del rango fisiológico, lo que lo hace robusto a los huecos de detección.')
    w.figura(FIG / 'aaron_brazadas.png', 'Señal de profundidad de la mano y brazadas detectadas (participante P1, secuencia GX011614).', clave='brazadas')
    w.p('En **vista frontal** (el nadador se aproxima a la cámara o se le registra desde el borde) la profundidad respecto '
        'al cuerpo no es observable. La señal pasa a ser el recorrido de cada muñeca respecto al centro de los hombros, '
        'proyectado sobre la dirección de máximo movimiento, obtenida como primera componente principal (PCA) de las '
        'posiciones de las muñecas con cada brazo centrado (Ecuación {eq:frontal}).')
    w.ecuacion('frontal', [('sub', 'q', 'j'), ('par', 't'), '=', ('frac', [('par', [('sub', 'w', 'j'), ('par', 't'), '−', 'h', ('par', 't')]), '·', ('sub', 'u', '1')],
                                                                ('sub', 'W', 'h'))],
               'Señal de recorrido de la muñeca en vista frontal',
               [('*q*_{j}(*t*)', 'recorrido de la muñeca *j* en anchos de hombros (adimensional)'),
                ('*u*_{1}', 'vector unitario de la primera componente principal del movimiento de las muñecas, orientado hacia abajo en la imagen'),
                ('*W*_{h}', 'ancho de hombros mediano en el vídeo (píxeles), más estable de frente que el tronco')])
    w.p('El estilo de nado determina cuántas brazadas forman un ciclo y el rango de tiempo plausible entre brazadas '
        '(Tabla {tab:estilos}).')
    w.tabla([
        ['Estilo', 'Brazadas por ciclo', 'Tiempo entre brazadas'],
        ['Crol', '2 (brazos alternos)', '0,35-1,0 s'],
        ['Espalda', '2 (brazos alternos)', '0,35-1,2 s'],
        ['Mariposa', '1 (brazos simultáneos)', '0,7-2,0 s'],
        ['Braza', '1 (brazos simultáneos)', '0,7-2,4 s'],
    ], 'Definición del ciclo de brazada según el estilo de nado.', clave='estilos', anchos=[4, 5, 5])

    w.h3('Vertical tabular: variables por ciclo')
    w.p('Para cada ciclo válido (duración entre 0,6 y 3,0 s y como máximo un 30 % de datos ausentes) se calculan las '
        'variables de la Tabla {tab:variables}.')
    w.tabla([
        ['Variable', 'Definición', 'Relación con la eficiencia y la fatiga'],
        ['Frecuencia de ciclo, SR (ciclos/min)', '60 / duración del ciclo', 'Aumenta como compensación con la fatiga'],
        ['DPS (m) y SI (m²/s)', 'Ecuaciones {eq:vel} y {eq:si}; requieren calibración', 'Principales indicadores de eficiencia'],
        ['Flexión del codo (°), izquierda y derecha', 'Percentil 10 del ángulo hombro-codo-muñeca', 'Eficacia de la fase subacuática'],
        ['Apertura del hombro (°)', 'Percentil 90 del ángulo codo-hombro-cadera', 'Extensión del brazo en la entrada'],
        ['Ángulo de cadera (°)', 'Media del ángulo hombro-cadera-rodilla', 'Alineación del cuerpo y arrastre'],
        ['Flexión de rodilla (°)', 'Percentil 10 del ángulo cadera-rodilla-tobillo', 'Calidad de la patada'],
        ['Alcance del brazo (relativo)', 'Recorrido de la muñeca sobre el eje del cuerpo (lateral) o recorrido *q* (frontal)', 'Longitud de la brazada'],
        ['Asimetría de brazos (%)', '100 · |alcance izq. − dcho.| / media', 'Descompensación lateral'],
        ['Inclinación del tronco (°)', 'Ángulo cadera-hombro respecto a la horizontal', 'Hundimiento de la cadera'],
        ['Amplitud de patada y patadas por ciclo', 'Separación de tobillos y número de máximos', 'Contribución y ritmo de la patada'],
    ], 'Variables calculadas por ciclo de brazada.', clave='variables', anchos=[4.8, 5.4, 5.8])
    w.p('Los ángulos y las distancias relativas no necesitan calibración. La velocidad, la DPS y el SI solo se calculan '
        'con cámara fija y anchura del encuadre conocida en metros; la velocidad se estima con la mediana del '
        'desplazamiento de la cadera entre fotogramas, robusta a los saltos de detección.')

    w.h3('Vertical tabular: detección del inicio de la fatiga')
    w.p('Ante la ausencia de etiquetas, la fatiga se modela como una anomalía respecto al estado inicial del propio '
        'nadador. El primer 30 % de los ciclos (como mínimo cinco) constituye la fase base, que se supone fresca. Cada '
        'variable se estandariza con la media y la desviación típica de esa fase (Ecuación {eq:z}).')
    w.ecuacion('z', [('sub', 'z', 'j'), '=', ('frac', [('sub', 'x', 'j'), '−', ('sub', 'μ', 'j')], ('sub', 'σ', 'j'))],
               'Estandarización respecto a la fase base',
               [('*x*_{j}', 'valor de la variable *j* en un ciclo (en sus unidades)'),
                ('μ_{j}, σ_{j}', 'media y desviación típica de la variable *j* en la fase base (mismas unidades)'),
                ('*z*_{j}', 'valor estandarizado, adimensional')])
    w.p('Sobre las variables estandarizadas se entrena un Isolation Forest de 500 árboles solo con la fase base, y cada '
        'ciclo recibe la puntuación de anomalía de la Ecuación {eq:ifscore}. El umbral es el percentil 95 de las '
        'puntuaciones de la fase base. El inicio de la fatiga es el primer ciclo posterior a la fase base a partir del '
        'cual la media móvil de tres ciclos supera el umbral durante al menos tres ciclos consecutivos. Como contraste '
        'independiente se aplica PELT (Ecuación {eq:pelt}) sobre la serie de puntuaciones; la coincidencia de ambos '
        'métodos refuerza la detección.')
    w.p('Para que la atribución sea interpretable se excluyen las variables redundantes: como la velocidad es el '
        'producto de SR y DPS (Ecuación {eq:vel}) y la potencia depende del cubo de la velocidad (Ecuación '
        '{eq:potencia}), el modelo no incluye la velocidad, el SI ni la potencia.')

    w.h3('Vertical tabular: atribución de la fatiga con SHAP')
    w.p('Sobre el Isolation Forest se calculan los valores SHAP exactos con TreeSHAP (Ecuaciones {eq:shapley} y '
        '{eq:shapadd}), con el signo invertido para que un valor positivo indique que la variable aproxima el ciclo a la '
        'fatiga. En cada ejecución se comprueba que la suma de los valores SHAP está positivamente correlacionada con la '
        'puntuación de anomalía. El sistema genera una explicación global (variables que más contribuyen a lo largo del '
        'nado), una explicación local del ciclo de inicio y un texto para el entrenador con las cuatro variables de '
        'mayor contribución y su cambio respecto a la fase base.')

    w.h3('Vertical tabular: clasificación del estilo de nado')
    w.p('El estilo se clasifica por ventanas de 4 s (desplazadas cada 2 s) con rasgos que no dependen de la definición '
        'del ciclo, para no introducir la etiqueta en su cálculo: correlación entre la señal de ambas manos (brazos '
        'simultáneos o alternos), posición de la nariz respecto a los hombros (decúbito prono o supino), correlación '
        'entre piernas, flexión máxima de la rodilla, separación de los pies, ondulación vertical de la cadera, periodo '
        'dominante del movimiento de las manos (obtenido por autocorrelación) y vista. El modelo es un bosque aleatorio '
        'de 300 árboles [@breiman2001] con imputación de valores ausentes por la mediana, evaluado con validación '
        'cruzada agrupada por vídeo (*GroupKFold*) para evitar la fuga de datos [@kaufman2012]; el estilo de un vídeo se '
        'obtiene promediando las probabilidades de sus ventanas. La atribución por estilo se calcula con TreeSHAP.')

    w.h3('Generación de datos sintéticos')
    w.p('Para evaluar el sistema con una referencia conocida se ha desarrollado un generador de datos sintéticos '
        '(`strokelab/simulador.py`). Produce los 17 puntos COCO de un nadador en vista lateral (cámara fija que abarca '
        'los 25 m de la piscina) o frontal, en cualquiera de los cuatro estilos. Brazos y piernas se calculan con '
        'cinemática inversa de dos segmentos para respetar las longitudes anatómicas. A partir de un instante '
        'programado, una función logística introduce la fatiga: aumenta la frecuencia de ciclo, disminuyen la velocidad, '
        'la distancia por ciclo y el alcance, se flexiona más el codo, se hunde la cadera y aparece asimetría. Se añaden '
        'ruido de posición, pérdida aleatoria de puntos, huecos de detección, virajes en las paredes y, opcionalmente, la '
        'copia del brazo oculto observada en los datos reales. El generador devuelve la referencia (frecuencia, '
        'velocidad y distancia por ciclo en cada instante), lo que permite medir el error del sistema.')

    w.h3('Análisis por sesión, por lotes y vídeo anotado')
    w.p('Cada secuencia de la cámara subacuática suele recoger una sola pasada de 10-20 s, insuficiente para observar '
        'fatiga. `sesion.py` concatena los ciclos de varias pasadas de un mismo nadador en orden de registro y aplica el '
        'mismo modelo. `lote.py` analiza todos los vídeos de una carpeta a partir de una lista editable (nadador, '
        'estilo, vista y sesión), puede reanudarse y rehace los análisis obtenidos con una versión anterior del código. '
        '`informe_nadador.py` resume un nadador y un estilo. El vídeo anotado (Figura {fig:panel}) muestra el estado '
        'FRESCO o FATIGA, el ciclo, la frecuencia y una barra temporal con la puntuación de cada ciclo, el umbral y el '
        'inicio de la fatiga.')
    w.figura(FIG / 'panel_video.png', 'Panel del vídeo anotado sobre datos sintéticos (t = 70 s; inicio de la fatiga en t = 51,9 s).', clave='panel', ancho_cm=13)
    w.h3('Conjunto de datos real')
    w.p('Los datos proceden de grabaciones de entrenamiento de un club de natación. De los '
        'vídeos disponibles, se seleccionaron para el análisis las secuencias en que el nadador aparece nadando un '
        'estilo identificable; se descartaron los vídeos de salida, viraje o reposo y los vídeos generados por el '
        'propio sistema (vídeos anotados), que no son datos de entrada. El conjunto final contiene **17 secuencias de '
        'cuatro participantes (P1 a P4) en los cuatro estilos**, con una duración total de 394,2 s (Tabla {tab:datos}).')
    w.tabla([
        ['Participante', 'Estilos', 'Secuencias (cámara subacuática / móvil)', 'Duración grabada', 'Vistas'],
        ['P1', 'Crol, mariposa', '4 / 3', '159,0 s', 'Lateral y frontal'],
        ['P2', 'Crol, espalda', '1 / 1', '62,5 s', 'Lateral y frontal'],
        ['P3', 'Crol, mariposa', '3 / 1', '97,6 s', 'Lateral y frontal'],
        ['P4', 'Braza', '2 / 2', '75,1 s', 'Lateral y frontal'],
        ['**Total**', '**4 estilos**', '**10 / 7**', '**394,2 s**', ''],
    ], 'Composición del conjunto de datos real.', clave='datos', anchos=[2.6, 3, 4.4, 2.8, 3.2])
    w.p('Se emplearon dos dispositivos. La cámara subacuática GoPro registra vídeo de 5120 × 2880 píxeles a 30 fps '
        'desde el lateral de la calle, con el nadador cruzando el encuadre; cada secuencia contiene una pasada de unos '
        '10-20 s en la que el nadador es visible. El teléfono móvil registra vídeo vertical de 1080 × 1920 píxeles a '
        '60 fps desde el borde de la piscina, con el nadador acercándose o alejándose de la cámara. Ninguna de las '
        'secuencias dispone de anotaciones de puntos articulares, por lo que la validación se apoya en el conteo manual '
        'de ciclos y en datos sintéticos de referencia conocida.')

    w.h3('Preparación de los datos y determinación de la vista')
    w.p('Antes del análisis, cada secuencia se describe en una lista editable (`lista_videos.csv`) con el código del '
        'participante, el estilo, la vista y la sesión. La vista no se fía solo a la indicación manual: durante la '
        'revisión del conjunto se comprobó que algunas secuencias de móvil estaban marcadas como laterales cuando el '
        'nadador se desplazaba hacia la cámara. Por ello, la vista se contrastó con un criterio objetivo, la mediana '
        'de la orientación del tronco en la imagen: con cámara lateral el eje hombros-cadera es casi horizontal '
        '(8-40°), mientras que de frente aparece casi vertical (más de 60°) y escorzado. Con este criterio, cinco '
        'secuencias de móvil se clasificaron como frontales y dos como laterales.')
    w.p('La preparación incluye, además: la anonimización de los participantes mediante códigos; la exclusión de los '
        'archivos de salida; la agrupación en sesiones por participante, estilo y dispositivo, ya que mezclar cámaras '
        'distintas alteraría la referencia de cada nadador; y el registro de la versión del análisis en cada '
        'resultado, de modo que el análisis por lotes rehace automáticamente los vídeos procesados con una versión '
        'anterior del código.')

    w.h3('Consideraciones éticas y protección de datos')
    w.p('Los vídeos contienen imágenes de personas identificables y constituyen datos personales. Su tratamiento se '
        'ha limitado a la finalidad académica del trabajo y requiere el consentimiento de los nadadores y, en el caso de '
        'menores, de sus tutores [PENDIENTE: indicar el consentimiento obtenido]. Se han aplicado las siguientes '
        'medidas:')
    w.vinetas([
        '**Minimización y anonimización.** En la memoria y en los resultados los participantes se identifican con un código (P1 a P4); no se publican nombres ni fotogramas en los que se reconozca a un nadador.',
        '**Procesamiento local.** El análisis se ejecuta en el ordenador personal de la autora; los vídeos no se envían a servicios externos de inferencia.',
        '**Datos derivados.** Los resultados que se comparten son series de puntos articulares y variables por ciclo, que no contienen la imagen del nadador.',
        '**Ausencia de decisiones automáticas.** El sistema ofrece información al entrenador, que conserva la decisión; los resultados no se emplean para evaluar ni seleccionar a los nadadores.',
    ])
    w.p('Con independencia del uso actual, una ampliación del estudio con menores de edad o con medidas fisiológicas '
        'requeriría la aprobación de un comité de ética y un consentimiento informado específico.')

    w.h3('Arquitectura del software y flujo de datos')
    w.p('El código se organiza en un paquete de Python (`strokelab`) con un módulo por etapa y varios programas de '
        'línea de órdenes que las combinan (Anexo B). Cada etapa lee y escribe archivos en una carpeta de resultados '
        'por vídeo, lo que permite repetir una etapa sin rehacer las anteriores: por ejemplo, recalcular los ciclos y '
        'la fatiga sin volver a estimar la pose, que es la etapa más costosa. La Tabla {tab:archivos} resume los '
        'archivos intermedios y su contenido.')
    w.tabla([
        ['Archivo', 'Etapa', 'Contenido'],
        ['keypoints_raw.npz', 'Pose 2D', 'Coordenadas y confianza de los 17 puntos por fotograma, resolución, fps y ajustes de detección'],
        ['keypoints_3d.npy', 'Elevación 3D', 'Coordenadas 3D normalizadas de los 17 puntos por fotograma'],
        ['medidas_por_fotograma.csv', 'Tabular', 'Ángulos, profundidad de la mano y señales de ciclo por fotograma'],
        ['variables_por_ciclo.csv', 'Tabular', 'Variables de cada ciclo válido, puntuación de anomalía y estado'],
        ['shap_por_ciclo.csv', 'Explicación', 'Valores SHAP de cada variable en cada ciclo'],
        ['resumen.json', 'Resumen', 'Versión, ajustes, detección, tiempo analizable, ciclos, inicio de la fatiga y explicación'],
        ['fig_*.png, *_ANOTADO.mp4', 'Presentación', 'Figuras de fatiga y SHAP y vídeo anotado'],
    ], 'Archivos generados por el análisis de un vídeo.', clave='archivos', anchos=[4.4, 2.6, 9])
    w.p('El análisis por lotes añade tres tablas agregadas: `resumen_lote.csv` (una fila por vídeo), '
        '`resumen_sesiones.csv` (una fila por sesión) y `ciclos_todos.csv` (todos los ciclos válidos con el '
        'participante, el estilo y la vista), así como un archivo comprimido con los resultados ligeros para su '
        'revisión. Esta separación entre la vertical de visión, que produce los puntos, y la vertical tabular, que los '
        'consume, materializa los modos de funcionamiento: el modo tabular acepta directamente los puntos o las '
        'variables por ciclo, sin vídeo.')
    w.p('Herramientas: Python 3, Ultralytics (YOLO), PyTorch (MotionBERT), OpenCV, NumPy, pandas, scikit-learn, shap, '
        'Matplotlib y Git. El código incluye pruebas automáticas que se ejecutan antes de cada cambio (Anexo C).')


def cap4_recursos(w):
    w.vinetas([
        'Ordenador personal con Windows y CPU de 4 hilos, sin GPU.',
        'Cámara subacuática GoPro (vídeo 5K a 30 fps) y teléfono móvil (1080 × 1920 píxeles, 60 fps).',
        'Vídeos de ocho nadadores de un club en los cuatro estilos, empleados exclusivamente con fines académicos.',
        'Software libre: Python y bibliotecas de código abierto; pesos preentrenados públicos de YOLOv8 y MotionBERT.',
        'Google Colab (gratuito) en la fase de prototipo y Google Drive para el intercambio de vídeos y resultados.',
    ])


def cap4_presupuesto(w):
    w.p('El presupuesto valora el tiempo invertido y el equipo utilizado, aunque no haya sido necesario adquirirlo. '
        'Todo el software es libre, por lo que su coste es nulo.').paragraph_format.keep_with_next = True


def cap4_viabilidad(w):
    w.p('El sistema es técnicamente viable con el equipo de un club: funciona en un ordenador personal sin GPU y '
        'procesa un vídeo 5K de 46 s en unos 9 minutos (288 s de estimación de pose, 25 s de elevación 3D y unos 205 s '
        'de vídeo anotado), sin coste de licencias. La principal condición es el protocolo de grabación: se necesita al '
        'menos un minuto de nado continuo, o varias pasadas de una misma sesión, para que la fatiga pueda manifestarse. '
        'El uso de los vídeos requiere el consentimiento de los nadadores.')


def cap4_resultados(w):
    w.h3('Métricas de evaluación')
    w.p('La exactitud de las magnitudes estimadas se mide con el error relativo frente a una referencia (Ecuación '
        '{eq:error}), que en los datos reales es el conteo manual y en los sintéticos el valor programado.')
    w.ecuacion('error', ['ε', '=', ('frac', ('bar', [('acc', 'x', '̂'), '−', 'x']), 'x'), '·', '100'],
               'Error relativo de una magnitud estimada',
               [('ε', 'error relativo (%)'), ('*x̂*', 'valor estimado por el sistema'), ('*x*', 'valor de referencia, en las mismas unidades')])
    w.p('La variabilidad de una medida entre ciclos se expresa con el coeficiente de variación (Ecuación {eq:cv}). La '
        'clasificación del estilo se evalúa con la exactitud (proporción de aciertos) por ventana y por vídeo, y con la '
        'matriz de confusión.')
    w.ecuacion('cv', ['CV', '=', ('frac', 'σ', 'μ'), '·', '100'], 'Coeficiente de variación',
               [('CV', 'coeficiente de variación (%)'), ('μ, σ', 'media y desviación típica de la medida entre ciclos (en sus unidades)')])

    w.h3('Validación con datos sintéticos: secuencia de 90 s')
    w.p('Se generó una secuencia sintética de crol de 90 s a 30 fps con fatiga progresiva centrada en t = 55 s y con los '
        'errores típicos del vídeo real: ruido, puntos de baja confianza, un hueco de detección, caderas sobre el hombro, '
        'esqueletos verticales y confusiones entre brazos. El sistema obtuvo 67 ciclos válidos y situó el **inicio de la '
        'fatiga en el ciclo 35 (t = 51,9 s)**, dentro de la transición introducida; PELT situó el cambio en el ciclo 33 '
        '(t = 49,4 s) y la correlación de comprobación del signo de SHAP fue 0,999 (Figuras {fig:sint_t} a {fig:sint_w}).')
    w.figura(FIG / 'sintetico_fatiga_timeline.png', 'Datos sintéticos: puntuación de anomalía por ciclo, umbral e inicio de la fatiga.', clave='sint_t')
    w.p('La atribución SHAP identifica como causas variables efectivamente alteradas: el alcance del brazo derecho '
        '(1,78 → 1,05 troncos), la asimetría de brazos (2 % → 23 %) y la amplitud de patada (0,31 → 0,21 troncos).')
    w.figura(FIG / 'sintetico_shap_summary.png', 'Datos sintéticos: atribución SHAP global de la puntuación de fatiga.', clave='sint_s', ancho_cm=12)
    w.figura(FIG / 'sintetico_shap_waterfall_inicio.png', 'Datos sintéticos: atribución SHAP local en el ciclo de inicio de la fatiga.', clave='sint_w', ancho_cm=12)

    w.h3('Validación con datos sintéticos: caso completo con referencia conocida')
    w.p('Para evaluar todas las capacidades se generó una secuencia sintética de crol de 120 s con cámara fija que '
        'abarca los 25 m (velocidad calibrada) y fatiga programada que pasa del 10 % al 90 % de su intensidad entre '
        't = 59 s y t = 81 s. Se analizó en vista lateral y frontal (Tabla {tab:caso}).')
    w.tabla([
        ['Medida', 'Vista lateral', 'Vista frontal'],
        ['Ciclos analizados', '91', '98'],
        ['Error relativo mediano de la frecuencia de ciclo', '4,7 %', '0,3 %'],
        ['Error relativo mediano de la velocidad', '1,3 %', 'No observable de frente'],
        ['Error relativo mediano de la distancia por ciclo', '4,3 %', 'No observable de frente'],
        ['Inicio de la fatiga detectado', 't = 57,3 s (ciclo 42)', 't = 57,8 s (ciclo 45)'],
        ['Variables con mayor atribución SHAP', 'Apertura del hombro (173° → 151°), asimetría de brazos (3 % → 24 %), inclinación del tronco (2,7° → 7,9°)',
         'Frecuencia de ciclo (46,2 → 52,9 ciclos/min), asimetría de brazos (1 % → 23 %), alcance del brazo (−32 %)'],
        ['Estilo predicho (probabilidad)', 'Crol (0,98)', 'Crol (0,95)'],
    ], 'Datos sintéticos: estimaciones del sistema frente a la referencia programada.', clave='caso', anchos=[5, 5.5, 5.5])
    w.p('El inicio de la fatiga se detecta al comienzo de la transición programada, cuando el cambio es todavía '
        'pequeño, lo que equivale a un aviso temprano. Las variables con mayor atribución son variables efectivamente '
        'alteradas en la simulación. La velocidad, la frecuencia y la distancia por ciclo estimadas siguen a la '
        'referencia a lo largo de toda la secuencia (Figura {fig:caso}). En vista frontal el error de la frecuencia es '
        'menor porque la señal sintética está libre de oclusiones; este valor no debe extrapolarse a datos reales.')
    w.figura(FIG / 'caso_verdad_vs_sistema.png', 'Datos sintéticos (vista lateral): velocidad, frecuencia y distancia por ciclo estimadas frente a la referencia.', clave='caso')

    w.h3('Clasificación del estilo de nado')
    w.p('El clasificador se evaluó con 64 vídeos sintéticos (4 estilos × 2 vistas × 8 nadadores con parámetros '
        'aleatorios), que suman 1216 ventanas, mediante validación cruzada agrupada por vídeo de cinco particiones. La '
        'exactitud fue del 99,8 % por ventana y del 100 % por vídeo (Figura {fig:estilo}). La atribución SHAP muestra que '
        'la posición de la nariz distingue el crol de la espalda, la simultaneidad de los brazos caracteriza la mariposa '
        'y la correlación entre piernas, la braza, lo que coincide con la definición biomecánica de cada estilo.')
    w.figura(FIG / 'caso_estilo.png', 'Clasificación del estilo en datos sintéticos: matriz de confusión por vídeo y atribución SHAP por estilo.', clave='estilo')
    w.p('Aplicado a las tres secuencias reales del participante P1, el clasificador no identifica correctamente el '
        'estilo. En vídeo real, el modelo de pose copia también las piernas (correlación entre piernas de 0,8-0,99) y la '
        'posición de la cabeza es menos marcada que en la simulación. El resultado pone de manifiesto la distancia entre '
        'el dominio sintético y el real (*domain gap*) y la necesidad de entrenar con vídeos reales etiquetados. Esta '
        'cuestión se evalúa con el conjunto real completo más adelante en esta sección.')

    w.h3('Datos reales: participante P1, crol')
    w.p('Se analizaron con `lote.py` las cinco secuencias disponibles del participante P1 en crol: tres de cámara '
        'subacuática en vista lateral (5120 × 2880 píxeles, 30 fps) y dos de teléfono móvil en vista frontal '
        '(1080 × 1920 píxeles, 60 fps). La vista frontal se identificó en los propios datos: en las secuencias de móvil '
        'el tronco aparece casi vertical en la imagen (78-102°) y mide 60-100 píxeles, frente a 8-10° en la cámara '
        'subacuática (Tabla {tab:p1} y Figura {fig:p1clips}).')
    w.tabla([
        ['Secuencia', 'Vista', 'Duración', 'Analizable', 'Ciclos', 'Frecuencia (ciclos/min)'],
        ['GX011614', 'Lateral', '46,2 s', '12,7 s', '9', '50,5'],
        ['GX011617', 'Lateral', '29,0 s', '7,0 s', '0', '—'],
        ['GX011618', 'Lateral', '28,2 s', '8,9 s', '1', '66,6'],
        ['IMG_7207', 'Frontal', '6,0 s', '5,1 s', '3', '73,9'],
        ['IMG_7215', 'Frontal', '9,4 s', '4,8 s', '4', '55,2'],
        ['**Total**', '', '**118,8 s**', '**38,5 s (32 %)**', '**17**', ''],
    ], 'Participante P1 (crol): tiempo analizable y ciclos válidos por secuencia.', clave='p1', anchos=[2.8, 2.2, 2.4, 3.2, 2, 3.4])
    w.figura(FIG / 'aaron_clips.png', 'Participante P1 (crol): tiempo analizable y ciclos válidos por secuencia.', clave='p1clips', ancho_cm=14)
    w.p('El factor limitante es la detección: en GX011617 el nadador permanece en el encuadre unos 19 s, pero el modelo '
        'lo detecta durante unos 5 s, la señal de la mano queda fragmentada y no se forman ciclos. Las opciones '
        '`--imgsz 1280` y `probar_deteccion.py` permiten evaluar si una entrada de mayor resolución recupera '
        'fotogramas; su estudio sistemático queda como trabajo futuro.')

    w.h3('Validación de la frecuencia de ciclo frente al conteo manual')
    w.tabla([
        ['Secuencia', 'Vista', 'Conteo manual', 'Sistema', 'Error relativo', 'Ciclos detectados'],
        ['GX011614 (s 30-40)', 'Lateral', '54 ciclos/min (9 ciclos en 10 s)', '50,5 ciclos/min', '6,5 %', '—'],
        ['IMG_7207 (completa)', 'Frontal', '80 ciclos/min (8 en 6,0 s)', '73,9 ciclos/min', '7,6 %', '3 de 8'],
        ['IMG_7215 (completa)', 'Frontal', '51 ciclos/min (8 en 9,4 s)', '55,2 ciclos/min', '8,2 %', '4 de 8'],
    ], 'Frecuencia de ciclo estimada frente al conteo manual. En GX011614, las versiones previas del método, que '
       'distinguían el brazo izquierdo del derecho, daban 79 y 34 ciclos/min.', clave='validacion', anchos=[3.6, 1.9, 4, 2.7, 2, 2.2])
    w.p('El error relativo de la frecuencia de ciclo (Ecuación {eq:error}) se sitúa entre el 6,5 % y el 8,2 % en las dos '
        'vistas, y el sistema distingue ritmos muy distintos de un mismo nadador (80 y 51 ciclos/min). La cobertura es '
        'baja: de frente se detecta entre el 38 % y el 50 % de los ciclos, a causa de la detección parcial. Las tres '
        'comparaciones forman parte de las pruebas automáticas del código.')

    w.h3('Medidas de la técnica del participante P1')
    w.p('Las medidas se resumen solo con las secuencias laterales, porque los ángulos 2D de vistas distintas no son '
        'comparables (Tabla {tab:medidas} y Figura {fig:p1var}). Los valores izquierdo y derecho se promedian, porque en '
        'vista lateral el modelo copia el brazo visible en el oculto.')
    w.tabla([
        ['Medida', 'Media', 'Desviación típica', 'CV'],
        ['Frecuencia de ciclo', '52,1 ciclos/min', '11,6 ciclos/min', '22 %'],
        ['Flexión del codo en el agarre', '125°', '16,6°', '13 %'],
        ['Apertura del hombro', '134°', '39,7°', '30 %'],
        ['Ángulo de cadera', '166°', '14,6°', '9 %'],
        ['Flexión de rodilla', '149°', '31,5°', '21 %'],
        ['Alcance del brazo', '2,08 troncos', '0,63 troncos', '30 %'],
        ['Inclinación del tronco', '8,5°', '4,1°', '49 %'],
        ['Amplitud de patada', '0,49 troncos', '0,29 troncos', '59 %'],
    ], 'Medidas por ciclo del participante P1 en crol (10 ciclos laterales). CV: coeficiente de variación (Ecuación {eq:cv}).',
        clave='medidas', anchos=[5.5, 3.5, 3.5, 2.5])
    w.figura(FIG / 'aaron_variables.png', 'Participante P1 (crol): valor de cada ciclo y mediana por secuencia.', clave='p1var')
    w.p('Un ángulo de cadera de 166° y una inclinación del tronco de 8,5° describen un cuerpo alineado y casi '
        'horizontal. Las variables de la extremidad inferior presentan la mayor variación entre ciclos (CV del 21 % al '
        '59 %), lo que coincide con que son las peor detectadas bajo el agua; sin más datos no deben interpretarse como '
        'cambios técnicos.')

    w.h3('Fatiga en datos reales')
    w.p('La sesión de cámara subacuática reúne 10 ciclos y **no se detecta fatiga sostenida**; la de móvil reúne 7, '
        'por debajo del mínimo de 8 que exige el método. Es el resultado esperado en pasadas de 10-20 s, y el sistema no '
        'genera falsas alarmas. En GX011614, sin fatiga, los valores SHAP son pequeños (≤ 0,1, frente a 0,4-0,6 en los '
        'datos sintéticos) y se concentran en la extremidad inferior: describen la variabilidad de la detección, no un '
        'cambio técnico. La localización de la fatiga en vídeo real requiere al menos unos 20 ciclos consecutivos '
        '(25-30 s de nado continuo); los datos sintéticos muestran el resultado que el sistema entrega en esa situación.')

    w.h3('Conjunto real completo: cobertura del análisis')
    w.p('El análisis por lotes se aplicó a las 17 secuencias del conjunto real con la misma configuración (YOLOv8n-Pose, '
        'un fotograma de cada dos, filtros anatómicos y de tronco girado). De los 394,2 s grabados, el sistema obtuvo '
        '**146,4 s analizables (37 %) y 100 ciclos válidos** (Figura {fig:conjunto}; detalle por secuencia en el '
        'Anexo D). La Tabla {tab:cobertura} agrega los resultados por participante y estilo.')
    w.figura(FIG / 'real_conjunto.png', 'Conjunto real: duración grabada, tiempo analizable y ciclos válidos por secuencia.', clave='conjunto')
    w.tabla([
        ['Participante y estilo', 'Secuencias', 'Grabado', 'Analizable', 'Ciclos válidos'],
        ['P1 · crol', '5', '118,8 s', '38,5 s (32 %)', '17'],
        ['P1 · mariposa', '2', '40,2 s', '12,6 s (31 %)', '7'],
        ['P2 · crol', '1', '49,6 s', '12,6 s (25 %)', '9'],
        ['P2 · espalda', '1', '12,9 s', '2,9 s (22 %)', '2'],
        ['P3 · crol', '1', '39,4 s', '7,4 s (19 %)', '3'],
        ['P3 · mariposa', '3', '58,2 s', '40,0 s (69 %)', '31'],
        ['P4 · braza', '4', '75,1 s', '32,4 s (43 %)', '31'],
        ['**Total**', '**17**', '**394,2 s**', '**146,4 s (37 %)**', '**100**'],
    ], 'Conjunto real: tiempo analizable y ciclos válidos por participante y estilo.', clave='cobertura', anchos=[4, 2.4, 2.6, 3.6, 3.4])
    w.p('La cobertura depende más de las condiciones de grabación que del estilo. Las dos secuencias de mariposa de P3 '
        '(GX010724 y GX010725) presentan la mayor proporción analizable (70-74 %), porque el nadador ocupa una '
        'parte grande del encuadre durante casi toda la secuencia. En cambio, en las secuencias largas de crol con cámara subacuática '
        '(GX011608, GX011609, GX011614) el nadador cruza el encuadre a distancia y solo se analiza entre el 19 % y el '
        '27 % del vídeo. Dos secuencias no producen ningún ciclo: GX011617, por la fragmentación de la señal ya '
        'descrita, e IMG_7209, en la que solo 1,6 s son analizables. El estilo espalda, con una única secuencia frontal '
        'de 2,9 s analizables, no tiene datos suficientes para ninguna conclusión.')

    w.h3('Frecuencia de ciclo y técnica por participante y estilo')
    w.p('La Tabla {tab:perfil} resume los ciclos laterales por participante y estilo; las secuencias frontales se '
        'excluyen porque sus ángulos 2D no son comparables. La Figura {fig:perfil} muestra la distribución por ciclo de '
        'tres variables.')
    w.tabla([
        ['Participante y estilo', 'Ciclos', 'Frecuencia (ciclos/min)', 'Codo (°)', 'Cadera (°)', 'Rodilla (°)', 'Inclinación (°)'],
        ['P1 · crol', '10', '52,1 ± 11,6', '125 ± 17', '166 ± 15', '149 ± 32', '8,5 ± 4,1'],
        ['P1 · mariposa', '7', '77,5 ± 9,9', '53 ± 23', '166 ± 4', '139 ± 10', '83,7 ± 2,5'],
        ['P2 · crol', '9', '66,7 ± 13,9', '80 ± 18', '147 ± 14', '130 ± 38', '18,2 ± 5,8'],
        ['P3 · crol', '3', '65,8 ± 11,0', '86 ± 31', '118 ± 30', '85 ± 56', '40,3 ± 11,2'],
        ['P3 · mariposa', '26', '57,5 ± 16,6', '103 ± 32', '163 ± 14', '126 ± 36', '15,2 ± 6,3'],
        ['P4 · braza', '29', '79,5 ± 17,1', '104 ± 43', '157 ± 14', '145 ± 28', '12,1 ± 5,8'],
    ], 'Variables por ciclo (media ± desviación típica) de los ciclos laterales por participante y estilo. Los ángulos '
       'son la media de los lados izquierdo y derecho.', clave='perfil', anchos=[3.0, 1.3, 2.8, 2.2, 2.2, 2.2, 2.3], size=8)
    w.figura(FIG / 'real_participantes.png', 'Distribución por ciclo de la frecuencia de ciclo, la flexión del codo y la inclinación del tronco por participante y estilo (ciclos laterales).', clave='perfil')
    w.p('Los perfiles deben leerse junto con la calidad de la detección, porque varios valores revelan errores de la '
        'pose más que rasgos técnicos:')
    w.vinetas([
        '**P1 · mariposa**: una inclinación del tronco de 84° es incompatible con el nado; indica que el modelo colocó un esqueleto casi vertical que superó el filtro de tronco girado, de modo que sus ángulos no son válidos.',
        '**P3 · crol**: con solo 3 ciclos, una cadera de 118° y una inclinación de 40°, los valores reflejan una detección deficiente y no se interpretan.',
        '**P4 · braza**: la frecuencia media de 79,5 ciclos/min, con ciclos de 95-100 ciclos/min (el límite que impone la duración mínima de 0,6 s), es superior a la habitual en braza. Es probable que la señal de la mano registre dos máximos por ciclo (tracción y recobro) y que la frecuencia esté sobrestimada; queda pendiente de validar con un conteo manual.',
        '**P1 · crol, P2 · crol y P3 · mariposa**: valores coherentes con la biomecánica del estilo (cuerpo alineado, inclinación de 8-18°, cadera de 147-166°); la frecuencia de P1 en crol está validada frente al conteo manual.',
    ])
    w.p('Con la cautela anterior, los dos nadadores de crol con detección suficiente muestran perfiles distintos: P2 '
        'nada con mayor frecuencia (66,7 frente a 52,1 ciclos/min), con el codo más flexionado en el agarre (80° '
        'frente a 125°) y con el tronco más inclinado (18,2° frente a 8,5°). La dispersión entre ciclos es elevada en '
        'todas las variables (coeficiente de variación del 13 % al 29 % en la frecuencia), lo que refuerza la decisión '
        'de comparar a cada nadador consigo mismo en lugar de con un patrón común.')

    w.h3('Fatiga en las sesiones reales')
    w.p('El análisis de fatiga se aplicó a todas las sesiones con al menos ocho ciclos, la condición mínima del método '
        '(Tabla {tab:sesiones}). En las tres sesiones que la cumplen no se detecta fatiga sostenida y PELT no '
        'encuentra ningún punto de cambio.')
    w.tabla([
        ['Sesión', 'Secuencias', 'Ciclos', 'Inicio de la fatiga', 'Cambio PELT', 'Resultado'],
        ['P1 · crol · cámara subacuática', '3', '10', 'No', 'No', 'Sin fatiga sostenida'],
        ['P3 · mariposa · cámara subacuática', '2', '26', 'No', 'No', 'Sin fatiga sostenida'],
        ['P4 · braza · cámara subacuática', '2', '27', 'No', 'No', 'Sin fatiga sostenida'],
        ['P1 · crol · móvil', '2', '7', '—', '—', 'Insuficiente (< 8 ciclos)'],
        ['P4 · braza · móvil', '2', '4', '—', '—', 'Insuficiente (< 8 ciclos)'],
    ], 'Resultado del análisis de fatiga en las sesiones reales con más de una secuencia.', clave='sesiones', anchos=[4.8, 2, 1.5, 2.5, 2.2, 3])
    w.figura(FIG / 'real_p4_fatiga_timeline.png', 'Participante P4 (braza, cámara subacuática): puntuación de anomalía por ciclo, umbral de la fase base y frecuencia y flexión del codo por ciclo.', clave='p4t')
    w.p('La sesión de P4 (Figura {fig:p4t}) ilustra el comportamiento del método en ausencia de fatiga: la puntuación '
        'oscila entre 0,45 y 0,55 alrededor del nivel de la fase base y solo un ciclo aislado supera el umbral, lo que '
        'no basta para declarar un inicio (se exigen tres ciclos consecutivos de la media móvil). Las variables por '
        'ciclo varían mucho de un ciclo al siguiente sin tendencia, lo que corresponde a variabilidad de la detección y '
        'no a una degradación progresiva. La atribución SHAP de la sesión (Figura {fig:p4s}) se concentra en la '
        'inclinación del tronco, el ángulo de cadera y el número de patadas por ciclo, con valores pequeños.')
    w.figura(FIG / 'real_p4_shap_summary.png', 'Participante P4 (braza): atribución SHAP de la puntuación de anomalía en la sesión, sin fatiga detectada.', clave='p4s', ancho_cm=12)
    w.p('El resultado es coherente con la naturaleza de los datos: las secuencias son pasadas cortas a ritmo de '
        'técnica, separadas por descansos, y no un esfuerzo continuo capaz de producir fatiga. Que el sistema no '
        'genere falsas alarmas en tres sesiones reales con 10, 26 y 27 ciclos es un resultado relevante, aunque no '
        'demuestra su capacidad de detectar la fatiga real, que solo podrá establecerse con grabaciones de nado '
        'continuo hasta el agotamiento.')

    w.h3('Clasificación del estilo con vídeos reales')
    w.p('Para cuantificar la transferencia del clasificador a datos reales se extrajeron los rasgos por ventana de las '
        'secuencias reales con suficiente señal: 42 ventanas de 11 vídeos (crol 4, mariposa 4, braza 3; la espalda no '
        'tiene ninguna ventana válida). Se compararon cinco esquemas de entrenamiento y evaluación frente a la '
        'referencia de asignar siempre la clase mayoritaria (Tabla {tab:estilo_real} y Figura {fig:estilo_real}).')
    w.tabla([
        ['Entrenamiento', 'Evaluación', 'Exactitud por ventana', 'Exactitud por vídeo'],
        ['— (clase mayoritaria)', '11 vídeos reales', '—', '36,4 %'],
        ['64 vídeos sintéticos', '11 vídeos reales', '16,7 %', '9,1 %'],
        ['Vídeos reales', 'Dejando un vídeo fuera', '47,6 %', '45,5 %'],
        ['Vídeos reales + sintéticos', 'Dejando un vídeo fuera', '42,9 %', '54,5 %'],
        ['Vídeos reales', 'Dejando un participante fuera', '9,5 %', '9,1 %'],
        ['Vídeos reales + sintéticos', 'Dejando un participante fuera', '19,0 %', '18,2 %'],
    ], 'Exactitud del clasificador de estilo sobre vídeos reales según el esquema de entrenamiento y evaluación.', clave='estilo_real', anchos=[4.6, 4.6, 3.4, 3.4])
    w.figura(FIG / 'real_estilo.png', 'Clasificación del estilo con vídeos reales: exactitud por vídeo según el esquema y atribución SHAP del modelo entrenado con vídeos reales.', clave='estilo_real')
    w.p('Los resultados muestran tres hechos. Primero, el modelo entrenado solo con datos sintéticos fracasa en vídeo '
        'real (9,1 %), por debajo de la referencia. La comparación de los rasgos explica el motivo: en la simulación la '
        'correlación entre piernas distingue con claridad el crol (−0,63) de la mariposa (0,95), mientras que en vídeo '
        'real vale 0,87-0,91 en todos los estilos, porque el modelo de pose copia la pierna visible en la oculta; lo '
        'mismo ocurre, en menor grado, con la correlación entre brazos (−0,41 en crol sintético frente a 0,31 en crol '
        'real). Segundo, con vídeos reales y dejando un vídeo fuera, la exactitud supera la referencia (45,5 %) y '
        'mejora al añadir los datos sintéticos (54,5 %). Tercero, dejando fuera un participante completo la exactitud '
        'cae al 9-18 %: en este conjunto el estilo está confundido con el nadador (P4 solo nada braza), de modo que el '
        'modelo aprende a reconocer al nadador o a la grabación más que el estilo.')
    w.p('En consecuencia, la clasificación automática del estilo con vídeo real **no está resuelta** con los datos '
        'disponibles, y el estilo se indica en la lista de vídeos. La atribución SHAP del modelo real apunta a los '
        'rasgos que sí conservan información (posición de la nariz, separación de los pies y simultaneidad de los '
        'brazos), lo que orienta la mejora: rasgos menos sensibles a la copia de extremidades y, sobre todo, más '
        'participantes por estilo.')

    w.h3('Análisis de sensibilidad del detector de fatiga (datos sintéticos)')
    w.p('Los parámetros del detector (proporción de la fase base, percentil del umbral y número de ciclos consecutivos '
        'exigidos) se fijaron a priori. Para evaluar su influencia se generaron, con datos sintéticos, 10 secuencias de '
        'crol de 120 s con fatiga programada (transición del 10 % al 90 % entre t = 59 s y t = 81 s) y 10 secuencias '
        'sin fatiga, con copia parcial de brazos y variabilidad entre ciclos. Se midió la tasa de detección en las '
        'secuencias con fatiga, la tasa de falsas alarmas en las secuencias sin fatiga y el instante medio de inicio '
        '(Tabla {tab:sensib} y Figura {fig:sensib}).')
    w.tabla([
        ['Fase base', 'Percentil', 'k = 2', 'k = 3', 'k = 4'],
        ['20 %', '90', '1,0 / 0,4 / 64,9 s', '1,0 / 0,3 / 67,3 s', '1,0 / 0,1 / 69,1 s'],
        ['20 %', '95', '1,0 / 0,1 / 71,8 s', '1,0 / 0,1 / 72,1 s', '1,0 / 0,1 / 74,3 s'],
        ['20 %', '99', '0,6 / 0,0 / 79,2 s', '0,5 / 0,0 / 75,2 s', '0,5 / 0,0 / 79,2 s'],
        ['30 %', '90', '1,0 / 0,3 / 60,3 s', '1,0 / 0,3 / 64,1 s', '1,0 / 0,1 / 66,4 s'],
        ['30 %', '95', '1,0 / 0,1 / 70,5 s', '**1,0 / 0,1 / 70,5 s**', '1,0 / 0,1 / 71,2 s'],
        ['30 %', '99', '0,8 / 0,1 / 84,8 s', '0,6 / 0,0 / 80,5 s', '0,6 / 0,0 / 83,8 s'],
        ['40 %', '90', '1,0 / 0,2 / 66,1 s', '1,0 / 0,2 / 66,1 s', '1,0 / 0,1 / 67,1 s'],
        ['40 %', '95', '1,0 / 0,1 / 68,8 s', '1,0 / 0,1 / 69,3 s', '1,0 / 0,1 / 70,4 s'],
        ['40 %', '99', '0,7 / 0,0 / 86,8 s', '0,6 / 0,0 / 85,9 s', '0,6 / 0,0 / 85,9 s'],
    ], 'Datos sintéticos: tasa de detección / tasa de falsas alarmas / inicio medio según la fase base, el percentil del '
       'umbral y los ciclos consecutivos k (10 secuencias con fatiga y 10 sin fatiga por configuración). En negrita, la '
       'configuración empleada.', clave='sensib', anchos=[2.2, 2.2, 3.85, 3.85, 3.85])
    w.figura(FIG / 'sint_sensibilidad.png', 'Datos sintéticos: inicio de la fatiga detectado (media ± desviación típica) según los parámetros del detector.', clave='sensib')
    w.p('El percentil del umbral es el parámetro decisivo. Con el percentil 90 la detección es completa, pero aparecen '
        'hasta un 40 % de falsas alarmas y el inicio se adelanta al comienzo de la transición. Con el percentil 99 '
        'desaparecen las falsas alarmas, pero se pierde entre el 20 % y el 50 % de las fatigas y las detectadas llegan '
        'tarde (75-87 s). El percentil 95 ofrece el mejor equilibrio en todas las combinaciones: detección del 100 %, '
        'falsas alarmas del 10 % e inicio medio entre 68,8 s y 74,3 s, dentro de la transición programada. La '
        'configuración elegida (30 %, percentil 95, k = 3) detecta el inicio en 70,5 ± 5,0 s, en el centro de la '
        'transición. La proporción de la fase base y el valor de k tienen un efecto menor: aumentar k reduce las falsas '
        'alarmas a costa de retrasar ligeramente el aviso.')

    w.h3('Robustez del conteo de ciclos (datos sintéticos)')
    w.p('Para separar el efecto de cada fuente de error sobre la frecuencia de ciclo se generaron secuencias '
        'sintéticas de crol en vista lateral de 60 s sin fatiga, con copia parcial de brazos (probabilidad 0,5) y con '
        'distintos niveles de ruido en la posición de los puntos y de pérdida de puntos (Tabla {tab:robustez}).')
    w.tabla([
        ['Ruido de posición', 'Pérdida 5 %', 'Pérdida 20 %', 'Pérdida 40 %'],
        ['1 píxel', '13,6 % (45,4)', '11,1 % (44,2)', '11,8 % (41,8)'],
        ['3 píxeles', '11,8 % (43,0)', '12,2 % (42,6)', '12,5 % (42,6)'],
        ['6 píxeles', '33,2 % (45,4)', '38,2 % (49,8)', '32,5 % (45,6)'],
    ], 'Datos sintéticos: error relativo mediano de la frecuencia de ciclo (y número medio de ciclos válidos) según el '
       'ruido de posición y la proporción de puntos perdidos.', clave='robustez', anchos=[4, 4, 4, 4])
    w.p('El conteo es robusto a la pérdida de puntos, incluso del 40 %, gracias a la interpolación de huecos cortos y a '
        'la mediana de los intervalos entre brazadas. El ruido de posición de hasta 3 píxeles apenas lo afecta, pero a '
        'partir de 6 píxeles aparecen máximos espurios y el error se triplica. La copia de brazos introduce por sí sola '
        'un error del 11-13 % (frente al 3-5 % sin copia), lo que confirma que la confusión entre brazos es la '
        'principal fuente de error del conteo en vista lateral y justifica el uso de la mano más profunda en lugar de '
        'cada brazo por separado. Los errores observados en vídeo real (6,5-8,2 %) son del mismo orden.')
    w.h3('Evaluación de la reconstrucción 3D frente a la 2D')
    w.tabla([
        ['Ángulo', 'Mediana 2D', 'Mediana 3D', 'Correlación'],
        ['Codo izq. / dcho.', '156° / 144°', '158° / 143°', '0,51 / −0,08'],
        ['Hombro izq. / dcho.', '90° / 81°', '89° / 92°', '0,69 / 0,71'],
        ['Cadera izq. / dcha.', '171° / 172°', '160° / 164°', '0,58 / 0,69'],
        ['Rodilla izq. / dcha.', '173° / 173°', '107° / 106°', '0,01 / −0,04'],
    ], 'Ángulos 2D frente a 3D en la vista lateral de la secuencia GX011614 (85 fotogramas).', clave='tresd', anchos=[4.5, 3.8, 3.8, 3.9])
    w.p('La reconstrucción 3D es coherente con la 2D en codo y cadera, pero no en la rodilla: sitúa la articulación en '
        '107°, como en una postura sentada, cuando la imagen la muestra casi extendida (173°), y comprime el rango del '
        'hombro. Por ello, en vista lateral los ángulos se calculan en 2D y el 3D se conserva por separado; en las '
        'vistas frontal y oblicua se emplea el 3D.')


# ---------------------------------------------------------------- capítulo 5

def cap5_discusion(w):
    w.p('Este capítulo analiza el grado de cumplimiento de las indicaciones recibidas, los cambios respecto al '
        'planteamiento inicial, las decisiones metodológicas y las limitaciones del trabajo.')
    w.h2('Respuesta a las indicaciones del director')
    w.tabla([
        ['Indicación', 'Implementación'],
        ['La explicabilidad (SHAP) es el eje del producto', 'Atribución global, local y textual de la fatiga y del estilo'],
        ['Dos verticales de IA: visión y datos tabulares', 'Visión (pose 2D y 3D) y tabular (variables, fatiga, estilo y SHAP) con un formato intermedio común'],
        ['Modos diferenciados', 'Modos vídeo y tabular implementados; audio como trabajo futuro'],
        ['Modelo hidrodinámico como conocimiento previo', 'Presentado en el Capítulo 2; la potencia no es variable de los modelos'],
        ['Optimizar el modelo de visión (MoveNet, ViTPose)', 'Comparativa en CPU; elegido YOLOv8n; MoveNet y MediaPipe como opciones; ViTPose como trabajo futuro'],
    ], 'Indicaciones del director y su implementación.', clave='indicaciones', anchos=[6, 10])
    w.h2('Cambios respecto al planteamiento inicial')
    w.vinetas([
        '**Solo vista lateral → vistas lateral y frontal.** Parte de los vídeos se registró de frente, donde la profundidad de la mano no es observable; se añadió una señal específica para esa vista.',
        '**MoveNet → YOLOv8n.** MoveNet se eligió por su fluidez, pero sobre vídeo subacuático YOLO detectó con el doble de confianza y produjo cinco veces más ciclos válidos.',
        '**Sensores inerciales → solo vídeo.** No se dispuso de sensores; la fusión con unidades inerciales queda como trabajo futuro.',
        '**Red recurrente supervisada → Isolation Forest no supervisado.** Sin etiquetas de fatiga, la comparación con el estado inicial del propio nadador no las requiere y admite una atribución SHAP exacta.',
        '**Potencia en vatios → indicadores cinemáticos.** La potencia depende de *C*_{D} y *A*, no medibles desde vídeo.',
        '**Validación por fotograma → validación por vídeo.** La exactitud del 99,99 % de una versión anterior era fuga de datos.',
        '**XGBoost → bosque aleatorio.** Para la clasificación del estilo, el bosque aleatorio evita una dependencia adicional y ofrece atribución SHAP exacta con un rendimiento suficiente.',
        '**Ejecución en Colab con GPU → ordenador personal en CPU.** Para un uso real en un club, sin coste y sin transferir los vídeos.',
    ])
    w.h2('Decisiones metodológicas')
    w.p('La comparación del nadador consigo mismo evita la necesidad de etiquetas y respeta la variabilidad individual '
        'descrita en la literatura. El análisis por ciclo reduce el ruido y la autocorrelación y produce unidades con '
        'significado para el entrenador. La exclusión de variables redundantes evita que SHAP reparta la importancia '
        'entre magnitudes dependientes. Por último, se ha priorizado lo observado sobre lo estimado: las brazadas se '
        'cuentan sobre la imagen 2D y los ángulos laterales son 2D, porque la evaluación mostró que el 3D falla en la '
        'extremidad inferior.')
    w.p('Respecto a la evaluación de la pose, la ausencia de anotaciones impide calcular OKS, PCK o mAP sobre los '
        'datos propios. La estrategia adoptada combina el rendimiento publicado en COCO, las métricas operativas en CPU '
        'y una validación orientada a la tarea (error de la frecuencia de ciclo). Esta última es la más relevante para '
        'el objetivo del sistema, aunque no sustituye una evaluación directa de la precisión de cada articulación.')
    w.h2('Interpretación de los resultados con datos reales')
    w.p('La aplicación al conjunto real completo permite separar lo que el sistema ya resuelve de lo que depende de '
        'los datos. La segmentación en ciclos y la frecuencia de ciclo funcionan en vídeo real con un error del 6,5 % '
        'al 8,2 % en crol, comparable al error que introduce la copia de brazos en los datos sintéticos (11-13 %), lo '
        'que indica que el conteo por la mano más profunda neutraliza en gran parte esa confusión. Las medidas '
        'angulares son plausibles cuando la detección es buena (P1 y P2 en crol, P3 en mariposa) y delatan los fallos '
        'de la pose cuando no lo es: una inclinación del tronco de 84° no es un rasgo técnico sino un esqueleto mal '
        'colocado. Este comportamiento es deseable, porque los errores se manifiestan en valores anómalos que el '
        'usuario puede reconocer, en lugar de quedar ocultos.')
    w.p('La cobertura del análisis (37 % del tiempo grabado) es el principal cuello de botella y depende sobre todo de '
        'la distancia entre la cámara y el nadador. El caso de P3 en mariposa, con un 70-74 % analizable, muestra que '
        'un encuadre más cerrado basta para multiplicar la información útil sin cambiar de modelo. Esta observación '
        'tiene una consecuencia práctica inmediata para el protocolo de grabación del club.')
    w.p('La ausencia de fatiga en las sesiones reales no permite afirmar que el detector funcione con nadadores '
        'reales, pero sí que no genera falsas alarmas en 63 ciclos repartidos en tres sesiones con variabilidad real '
        'de la detección. El análisis de sensibilidad con datos sintéticos, que estima una tasa de falsas alarmas del '
        '10 % con la configuración elegida, es coherente con ese resultado. Ambos resultados son complementarios: los '
        'datos sintéticos cuantifican la capacidad de detección y los reales, el comportamiento ante la variabilidad '
        'de la pose sin fatiga.')
    w.p('Por último, la clasificación del estilo ilustra la distancia entre dominios: un modelo perfecto en datos '
        'sintéticos (100 %) falla en vídeo real (9,1 %) porque los rasgos que lo hacen perfecto, la alternancia de '
        'piernas y brazos, son precisamente los que el modelo de pose no reproduce bajo el agua. La explicabilidad '
        'resulta aquí útil no solo para el entrenador sino para el desarrollador: comparar los rasgos y su atribución '
        'SHAP en ambos dominios permite localizar la causa del fallo.')

    w.h2('Comparación con trabajos relacionados')
    w.p('Los trabajos de estimación de pose en natación se centran en la precisión de los puntos articulares en '
        'condiciones controladas [@einfalt2018; @fiche2023] y emplean conjuntos anotados o generados por ordenador. '
        'StrokeLab no compite en esa precisión, que no puede medir sin anotaciones, sino que aborda un problema '
        'posterior: convertir una pose imperfecta en indicadores por ciclo y en una explicación de la fatiga. La '
        'literatura biomecánica describe la fatiga como un aumento de la frecuencia de ciclo con descenso de la '
        'distancia por ciclo y cambios de coordinación [@craig1979; @alberty2005; @chollet2000]; estas son las '
        'variables que el sistema modela y, en los datos sintéticos, las que la atribución SHAP señala. La diferencia '
        'principal respecto a los sistemas instrumentados es el coste y la ausencia de sensores; la principal desventaja, '
        'la menor precisión de la medida y la dependencia de la calidad del vídeo.')

    w.h2('Amenazas a la validez')
    w.vinetas([
        '**Validez interna.** Los parámetros del detector se fijaron antes del análisis de sensibilidad, que confirma que la configuración elegida se sitúa en la zona de mejor equilibrio; no se han ajustado a los datos reales, lo que evita un sesgo optimista. El simulador fue diseñado por la autora, de modo que los datos sintéticos pueden favorecer al método; por ello se presentan siempre separados de los reales.',
        '**Validez de constructo.** El sistema mide la *fatiga técnica*, entendida como el cambio sostenido de la técnica respecto al estado inicial; no mide la fatiga fisiológica. Un cambio técnico voluntario (por ejemplo, un cambio de ritmo) se detectaría igualmente como anomalía.',
        '**Validez externa.** Cuatro participantes de un mismo club, grabados con dos dispositivos, no representan la variedad de nadadores, piscinas y cámaras; los resultados no deben generalizarse sin nuevos datos.',
        '**Fiabilidad de la referencia.** El conteo manual de ciclos fue realizado por una sola persona y sin repetición, por lo que su error propio no está cuantificado.',
    ])
    w.h2('Limitaciones')
    w.vinetas([
        '**Escasez de datos reales.** El conjunto real suma 17 secuencias cortas de cuatro participantes (146 s analizables y 100 ciclos); varios estilos tienen un solo participante y la espalda carece de datos suficientes. No existe todavía una validación experimental de la fatiga en nadadores reales.',
        '**Estilo confundido con el participante.** Al nadar P4 solo braza, el clasificador de estilo con vídeos reales no puede separar el estilo del nadador; su exactitud con participantes no vistos es inferior a la referencia.',
        '**Validación manual limitada.** El conteo manual cubre tres secuencias de crol; la frecuencia de los demás estilos, en particular la braza, no se ha validado.',
        '**Referencia de la fatiga.** No se ha contrastado el inicio detectado con una medida independiente (lactato, esfuerzo percibido o valoración experta).',
        '**Una sola cámara.** Los ángulos 2D son proyecciones; la refracción y la rotación del cuerpo los distorsionan.',
        '**Brazos y piernas indistinguibles en vista lateral.** La asimetría y los ángulos de cada lado son poco fiables en esa vista.',
        '**Detección parcial.** El nadador es analizable en torno a un tercio del vídeo y, de frente, se detecta entre el 38 % y el 50 % de los ciclos.',
        '**Vista indicada por el usuario.** Un error en la vista empeora el conteo (con la señal frontal en una secuencia lateral el error pasó del 6,5 % al 14 %).',
        '**Fase base.** Se supone que el nadador comienza descansado; si no es así, el inicio de la fatiga se subestima.',
        '**Datos sintéticos.** Validan el método, pero son más regulares que los reales; el clasificador de estilo no se transfiere todavía a vídeo real.',
    ])


# ---------------------------------------------------------------- capítulos 6 y 7

def cap6_trabajo(w):
    w.p('Se ha desarrollado un sistema completo de análisis biomecánico explicable que funciona en la CPU de un '
        'ordenador personal y que transforma un vídeo de nado en indicadores de eficiencia, inicio de la fatiga técnica '
        'y atribución por variable. La Tabla {tab:objetivos} resume el grado de cumplimiento de los objetivos.')
    w.tabla([
        ['Objetivo', 'Resultado', 'Grado'],
        ['OE1. Selección del modelo de pose', 'Comparativa en CPU; YOLOv8n-Pose elegido y justificado', 'Cumplido'],
        ['OE2. Elevación a 3D', 'Implementada y evaluada; válida en codo y cadera, no en rodilla', 'Cumplido con limitaciones'],
        ['OE3. Ciclos de brazada', 'Error de la frecuencia del 6,5-8,2 % frente al conteo manual', 'Cumplido'],
        ['OE4. Variables por ciclo', 'Eficiencia y ángulos de codo, hombro, cadera, rodilla y pies', 'Cumplido'],
        ['OE5. Inicio de la fatiga', 'Validado con datos sintéticos (detección 100 %, falsas alarmas 10 %); sin falsas alarmas en tres sesiones reales; sin fatiga real que detectar', 'Parcial'],
        ['OE6. Atribución con SHAP', 'Global, local y textual; coincide con las variables alteradas', 'Cumplido'],
        ['OE7. Clasificación del estilo', '100 % por vídeo en datos sintéticos; 45,5 % en vídeo real (referencia 36,4 %); no generaliza a participantes nuevos', 'Parcial'],
        ['OE8. Vídeo anotado', 'Panel de fatiga por ciclo', 'Cumplido'],
        ['OE9. Evaluación con datos sintéticos', 'Generador con referencia conocida y pruebas automáticas', 'Cumplido'],
    ], 'Grado de cumplimiento de los objetivos específicos.', clave='objetivos', anchos=[5, 7.5, 3.5])
    w.p('Con datos sintéticos de referencia conocida, el sistema estima la frecuencia de ciclo, la velocidad y la '
        'distancia por ciclo con errores medianos inferiores al 5 %, detecta el inicio de la fatiga al comienzo de la '
        'transición programada y atribuye la fatiga a las variables alteradas. Con vídeo real, la frecuencia de ciclo '
        'se aproxima al conteo manual con un error del 6,5 % al 8,2 % en dos vistas, y las medidas del participante P1 '
        'describen un crol con el cuerpo alineado. Aplicado a 17 secuencias reales de cuatro participantes y cuatro '
        'estilos, el sistema obtuvo 100 ciclos válidos y perfiles técnicos diferenciados por nadador, y no detectó '
        'fatiga en ninguna de las tres sesiones con datos suficientes, lo que es coherente con su duración. El análisis '
        'de sensibilidad confirma que la configuración del detector ofrece el mejor equilibrio entre detección y falsas '
        'alarmas, y la evaluación con vídeos reales muestra que la clasificación del estilo necesita más participantes '
        'por estilo para generalizar.')
    w.p('La principal debilidad del trabajo no reside en el modelo ni en la arquitectura, sino en la escasez de datos '
        'reales y en la ausencia de una validación experimental de la fatiga en nadadores reales. El sistema está '
        'preparado para esa validación en cuanto se disponga de grabaciones de nado continuo y de una referencia '
        'fisiológica.')


def cap6_personales(w):
    w.p('Este trabajo me ha enseñado que, en un proyecto de inteligencia artificial aplicada, la calidad de los datos '
        'pesa más que la elección del modelo. Descubrir que la exactitud del 99,99 % de una versión anterior era fuga '
        'de datos fue la lección más importante: desde entonces he contrastado cada resultado con una referencia, ya '
        'fuera un conteo manual o un conjunto de datos sintéticos con valores conocidos.')
    w.p('También he aprendido a adaptar herramientas concebidas para personas de pie a un entorno tan distinto como el '
        'agua, y a presentar los resultados de forma que un entrenador pueda utilizarlos. Trabajar con un ordenador '
        'sin GPU me obligó a priorizar soluciones ligeras y a medir su coste real. Me llevo, sobre todo, la importancia '
        'de ser rigurosa con lo que un sistema puede y no puede afirmar.')


def cap7_futuro(w):
    w.p('Las líneas de trabajo futuras se derivan directamente de las limitaciones identificadas y se agrupan en cuatro '
        'ámbitos: los datos y la validación experimental, los modelos de visión, la extensión del sistema y su '
        'aplicación práctica.')
    w.h2('Datos y validación experimental')
    w.p('La prioridad es la validación experimental de la fatiga en nadadores reales. Para ello se propone un protocolo '
        'de grabación de series largas de nado continuo (por ejemplo, 400 m o series hasta el agotamiento) con cámara '
        'lateral fija y calibrada, acompañado de referencias independientes del estado de fatiga: concentración de '
        'lactato en sangre, escala de esfuerzo percibido y valoración experta del entrenador. Con esos datos podría '
        'medirse la concordancia entre el ciclo de inicio detectado y la referencia, y estimarse la sensibilidad y la '
        'especificidad del método.')
    w.p('En paralelo, la anotación manual de un conjunto de fotogramas subacuáticos permitiría calcular las métricas '
        'estándar de estimación de pose (OKS, PCK y mAP) sobre los datos propios y comparar los modelos con el mismo '
        'criterio que la literatura. La ampliación del estudio a los ocho nadadores disponibles y a los cuatro estilos '
        'permitiría, además, comparar patrones individuales de fatiga.')
    w.h2('Modelos de visión')
    w.p('El ajuste fino de los modelos de pose con imágenes de natación, procedentes de SwimXYZ y de fotogramas propios '
        'anotados, debería mejorar la detección bajo el agua y la distinción entre el brazo izquierdo y el derecho. Con '
        'un conjunto anotado suficiente cabría desarrollar un modelo propio especializado en natación. Del mismo modo, '
        'la adaptación de MotionBERT a nadadores, con datos de captura de movimiento acuático o sintéticos, permitiría '
        'obtener ángulos 3D fiables en la extremidad inferior. Cuando se disponga de GPU, ViTPose y otros modelos de '
        'mayor precisión podrán evaluarse con el mismo protocolo.')
    w.h2('Extensión del sistema')
    w.p('El modo audio, que estimaría la frecuencia de brazada y el patrón respiratorio a partir del sonido, '
        'completaría los modos de entrada previstos. La fusión con sensores inerciales permitiría medir la velocidad sin '
        'calibrar la cámara. La detección automática de la vista a partir de la orientación del tronco eliminaría la '
        'dependencia de la indicación del usuario, y el entrenamiento del clasificador de estilo con vídeos reales '
        'etiquetados reduciría la distancia entre el dominio sintético y el real.')
    w.h2('Aplicación práctica')
    w.p('Por último, una versión con procesamiento en tiempo casi real y una interfaz para el entrenador facilitarían '
        'su uso diario en el club. Un sistema de grabación con cámara que acompañe al nadador permitiría analizar series '
        'completas de nado continuo, condición necesaria para observar la fatiga en entrenamientos reales.')


def anexos(w):
    w.h2('Anexo A. Guía de ejecución')
    for t in ['pip install -r requirements.txt',
              'python diagnostico.py',
              'python analizar.py "videos/GX011614.MP4" --nadador "P1" --estilo crol --vista lateral',
              'python analizar.py "videos/GX011614.MP4" --comparativa',
              'python lote.py --carpeta videos --crear-lista      (y después sin --crear-lista)',
              'python sesion.py resultados/GX011614 resultados/GX011617 resultados/GX011618 --nadador "P1"',
              'python informe_nadador.py resultados --nadador P1 --estilo crol',
              'python caso_ficticio.py      (datos sintéticos de referencia conocida)']:
        w.p(f'`{t}`', alinear='izq', size=9)
    w.p('Salidas en la carpeta de resultados: puntos 2D y 3D, medidas por fotograma, variables por ciclo, valores SHAP '
        'por ciclo, resumen en formato JSON, figuras y vídeo anotado.')
    w.h2('Anexo B. Estructura del código')
    w.tabla([
        ['Archivo', 'Función'],
        ['analizar.py', 'Programa principal: pose, limpieza, 3D, medidas, fatiga y vídeo'],
        ['strokelab/pose.py', 'Modelos de pose (YOLO, MoveNet, MediaPipe), giro y comparativa'],
        ['strokelab/lift3d.py', 'Elevación a 3D con MotionBERT adaptada a nadadores'],
        ['strokelab/medidas.py', 'Limpieza, filtros anatómicos, ángulos, ciclos y variables'],
        ['strokelab/fatiga.py', 'Isolation Forest, PELT, SHAP y explicación textual'],
        ['strokelab/estilo.py', 'Clasificación del estilo con bosque aleatorio y SHAP'],
        ['strokelab/simulador.py', 'Generación de datos sintéticos con referencia conocida'],
        ['strokelab/video.py', 'Vídeo anotado con el panel de fatiga'],
        ['sesion.py, lote.py', 'Análisis por sesión y de conjuntos de vídeos'],
        ['informe_nadador.py', 'Informe de un nadador y un estilo'],
        ['caso_ficticio.py', 'Caso de evaluación completo con datos sintéticos'],
        ['probar_deteccion.py, validar_3d.py', 'Ajustes de detección y comparación 2D-3D'],
    ], 'Módulos del código de StrokeLab.', clave='codigo', anchos=[5, 11])
    w.h2('Anexo C. Pruebas automáticas')
    w.vinetas([
        '`tests/test_local.py`: datos sintéticos con errores típicos; exige detectar la fatiga entre 40 y 60 s y medidas plausibles.',
        '`tests/test_sesion.py`: datos sintéticos divididos en pasadas, con una pasada vacía.',
        '`tests/test_aaron.py`: secuencia real GX011614; exige una frecuencia a menos de un 15 % del conteo manual.',
        '`tests/test_aaron_frontal.py`: secuencias reales frontales; mismo criterio.',
        '`tests/test_frontal.py`: datos sintéticos en vista frontal con fatiga.',
        '`tests/test_estilos.py`: ciclos de mariposa (1 brazada) y de crol (2 brazadas).',
        '`tests/test_simulador_estilo.py`: errores de frecuencia y velocidad frente a la referencia y exactitud del clasificador de estilo.',
        '`tests/test_lote.py` y `tests/test_movenet_recorte.py`: análisis por lotes y conversión de coordenadas.',
    ])

    w.h2('Anexo D. Resultados por secuencia del conjunto real')
    w.tabla([
        ['Secuencia', 'Part.', 'Estilo', 'Vista', 'Duración', 'Detección bruta', 'Analizable', 'Ciclos', 'Frecuencia (ciclos/min)'],
        ['GX011614', 'P1', 'Crol', 'Lateral', '46,2 s', '96 %', '12,7 s', '9', '50,5'],
        ['GX011617', 'P1', 'Crol', 'Lateral', '29,0 s', '95 %', '7,0 s', '0', '—'],
        ['GX011618', 'P1', 'Crol', 'Lateral', '28,2 s', '100 %', '8,9 s', '1', '66,6'],
        ['IMG_7207', 'P1', 'Crol', 'Frontal', '6,0 s', '98 %', '5,1 s', '3', '73,9'],
        ['IMG_7215', 'P1', 'Crol', 'Frontal', '9,4 s', '100 %', '4,8 s', '4', '55,2'],
        ['GX011610', 'P1', 'Mariposa', 'Lateral', '30,8 s', '98 %', '11,0 s', '7', '77,5'],
        ['IMG_7209', 'P1', 'Mariposa', 'Lateral', '9,5 s', '83 %', '1,6 s', '0', '—'],
        ['GX011608', 'P2', 'Crol', 'Lateral', '49,6 s', '93 %', '12,6 s', '9', '66,7'],
        ['IMG_7205', 'P2', 'Espalda', 'Frontal', '12,9 s', '100 %', '2,9 s', '2', '54,6'],
        ['GX011609', 'P3', 'Crol', 'Lateral', '39,4 s', '81 %', '7,4 s', '3', '65,8'],
        ['GX010724', 'P3', 'Mariposa', 'Lateral', '22,6 s', '99 %', '16,5 s', '13', '61,8'],
        ['GX010725', 'P3', 'Mariposa', 'Lateral', '21,4 s', '100 %', '15,8 s', '13', '53,3'],
        ['IMG_7204', 'P3', 'Mariposa', 'Frontal', '14,1 s', '96 %', '7,7 s', '5', '47,3'],
        ['GX011611', 'P4', 'Braza', 'Lateral', '27,0 s', '99 %', '8,7 s', '9', '82,2'],
        ['GX011616', 'P4', 'Braza', 'Lateral', '31,7 s', '100 %', '15,6 s', '18', '79,7'],
        ['IMG_7213', 'P4', 'Braza', 'Lateral', '9,1 s', '97 %', '3,0 s', '2', '64,8'],
        ['IMG_7217', 'P4', 'Braza', 'Frontal', '7,3 s', '97 %', '5,1 s', '2', '39,7'],
    ], 'Resultados del análisis por secuencia del conjunto real. La detección bruta es la proporción de fotogramas '
       'analizados con alguna persona detectada, antes de los filtros; el tiempo analizable es el que supera los '
       'filtros anatómicos y de tronco girado.', clave='anexo_videos', anchos=[2.5, 1.2, 1.8, 1.6, 1.6, 1.8, 1.8, 1.3, 2.4], size=8)
    w.h2('Anexo E. Parámetros del sistema')
    w.tabla([
        ['Etapa', 'Parámetro', 'Valor', 'Justificación'],
        ['Pose 2D', 'Modelo', 'YOLOv8n-Pose', 'Mejor detección en vídeo subacuático en CPU (Capítulo 4)'],
        ['Pose 2D', 'Fotogramas analizados', '1 de cada 2', 'Reduce el tiempo a la mitad; 15 fps bastan para ciclos de 1-2 s'],
        ['Pose 2D', 'Lado máximo de la imagen', '1920 píxeles', 'Evita el coste de procesar el vídeo 5K completo'],
        ['Pose 2D', 'Giro del fotograma', 'Automático (0°, ±90°)', 'El modelo detecta mejor personas verticales'],
        ['Limpieza', 'Confianza mínima de un punto', '0,3', 'Descarta puntos inciertos antes de interpolar'],
        ['Limpieza', 'Tronco girado', '> 45° de la dirección habitual', 'Elimina esqueletos verticales espurios'],
        ['Limpieza', 'Longitud del tronco', '0,5-2 × mediana', 'Elimina caderas colocadas sobre el hombro'],
        ['Limpieza', 'Suavizado', 'Savitzky-Golay', 'Conserva máximos y mínimos de la señal'],
        ['Ciclos', 'Intervalo entre brazadas (crol)', '0,35-1,0 s', 'Rango fisiológico de 30-85 ciclos/min'],
        ['Ciclos', 'Intervalo entre brazadas (mariposa / braza)', '0,7-2,0 s / 0,7-2,4 s', 'Un ciclo por brazada'],
        ['Ciclos', 'Duración de un ciclo válido', '0,6-3,0 s, ≤ 30 % de datos ausentes', 'Descarta ciclos partidos o fusionados'],
        ['Ciclos', 'Mínimo y máximo por ciclo', 'Percentiles 10 y 90', 'Un fotograma erróneo no fija el valor del ciclo'],
        ['Fatiga', 'Fase base', 'Primer 30 % de los ciclos (mínimo 5)', 'Análisis de sensibilidad (Tabla {tab:sensib})'],
        ['Fatiga', 'Isolation Forest', '500 árboles', 'Estabilidad de la puntuación'],
        ['Fatiga', 'Umbral', 'Percentil 95 de la fase base', 'Mejor equilibrio entre detección y falsas alarmas'],
        ['Fatiga', 'Inicio', 'Media móvil de 3 ciclos sobre el umbral durante 3 ciclos', 'Evita avisos por ciclos aislados'],
        ['Fatiga', 'Mínimo de ciclos', '8', 'Fase base de al menos 5 ciclos y margen de observación'],
        ['Fatiga', 'PELT', 'Coste L2, penalización 2 ln n', 'Criterio de información estándar'],
        ['Estilo', 'Ventanas', '4 s cada 2 s', 'Al menos dos ciclos por ventana'],
        ['Estilo', 'Bosque aleatorio', '300 árboles, 2 muestras por hoja', 'Rendimiento estable sin ajuste fino'],
    ], 'Parámetros principales del sistema y su justificación.', clave='parametros', anchos=[1.8, 4.2, 4.4, 5.6], size=8)
    w.h2('Anexo F. Diccionario de variables por ciclo')
    w.tabla([
        ['Variable', 'Unidad', 'Definición'],
        ['SR_ciclos_min', 'ciclos/min', 'Frecuencia de ciclo: 60 dividido por la duración del ciclo'],
        ['velocidad_m_s', 'm/s', 'Velocidad media de la cadera en el ciclo (solo vista lateral calibrada)'],
        ['DPS_m', 'm', 'Distancia por ciclo: velocidad por duración del ciclo'],
        ['codo_min_I / _D', 'grados', 'Flexión máxima del codo en el ciclo (percentil 10 del ángulo)'],
        ['hombro_max_I / _D', 'grados', 'Apertura máxima del hombro (percentil 90 del ángulo tronco-brazo)'],
        ['cadera_media_I / _D', 'grados', 'Ángulo medio de la cadera (alineación tronco-muslo)'],
        ['rodilla_min_I / _D', 'grados', 'Flexión máxima de la rodilla (percentil 10)'],
        ['alcance_I / _D', 'troncos', 'Recorrido de la muñeca en el ciclo, relativo a la longitud del tronco'],
        ['asimetria_brazos_pct', '%', 'Diferencia de alcance entre brazos dividida por su media'],
        ['inclinacion_tronco', 'grados', 'Ángulo medio del eje hombros-cadera respecto a la horizontal de la imagen (solo vista lateral)'],
        ['amplitud_patada', 'troncos', 'Separación máxima entre los tobillos en el ciclo, relativa a la longitud del tronco'],
        ['patadas_por_ciclo', 'patadas', 'Número de máximos de la separación entre tobillos en el ciclo'],
        ['anomalia, estado', '—, texto', 'Puntuación de Isolation Forest y estado FRESCO o FATIGA'],
    ], 'Variables por ciclo del archivo variables_por_ciclo.csv.', clave='diccionario', anchos=[4, 2.2, 9.8], size=8)

# ---------------------------------------------------------------- montaje

def construir():
    EST['cont'] = {}
    EST['citas_pasada'] = []
    doc = docx.Document(str(PLANTILLA))
    if 'Caption' not in [s.name for s in doc.styles]:
        st = doc.styles.add_style('Caption', 1)
        st.base_style = doc.styles['Normal']
        st.font.size = Pt(9); st.font.italic = True
        st.paragraph_format.space_after = Pt(8)
    # Índice alineado: «Capítulo n.» seguido de un espacio (no de un tabulador) y tabulador derecho con puntos
    num = doc.part.numbering_part.element
    for an in num.findall(qn('w:abstractNum')):
        if an.get(qn('w:abstractNumId')) == '7':
            for lv in an.findall(qn('w:lvl')):          # capítulo y apartados: número + espacio
                if lv.find(qn('w:suff')) is None and lv.find(qn('w:lvlText')) is not None:
                    suff = OxmlElement('w:suff'); suff.set(qn('w:val'), 'space')
                    lv.find(qn('w:lvlText')).addprevious(suff)
    for nombre in ('toc 1', 'toc 2', 'toc 3'):
        doc.styles[nombre].paragraph_format.tab_stops.add_tab_stop(Cm(15), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)

    b = list(doc.element.body.iterchildren())
    P = lambda i: Paragraph(b[i], doc._body)  # noqa: E731
    ppr_vineta = copy.deepcopy(b[64].find(qn('w:pPr')))
    for e in ppr_vineta.findall(qn('w:rPr')):
        ppr_vineta.remove(e)

    # portada
    poner_texto(P(8), 'MÁSTER UNIVERSITARIO EN INTELIGENCIA ARTIFICIAL')
    poner_texto(P(11), TITULO, size=12)
    poner_texto(P(13), AUTORA)
    poner_texto(P(14), 'Dirigido por')
    poner_texto(P(15), DIRECTOR)
    poner_texto(P(16), 'CURSO 2025-2026')
    poner_texto(P(17), f'TÍTULO: {TITULO}')
    poner_texto(P(19), f'AUTOR: {AUTORA}')
    poner_texto(P(21), 'TITULACIÓN: Máster Universitario en Inteligencia Artificial')
    poner_texto(P(23), f'DIRECTOR/ES DEL PROYECTO: {DIRECTOR}')
    poner_texto(P(26), 'FECHA: octubre de 2026')
    for s in doc.sections:
        for h in (s.header, s.first_page_header, s.even_page_header):
            for par in h.paragraphs:
                if 'Título Proyecto' in par.text:
                    poner_texto(par, TITULO_CORTO)
                elif 'Apellido1' in par.text:
                    poner_texto(par, 'Diana Cruz')

    t = Table(b[128], doc._body)
    for fila, txt in zip(range(1, 8), [AUTORA, TITULO, DIRECTOR, 'NO', 'SÍ', 'SÍ',
                                       'Desarrollar un sistema de inteligencia artificial explicable que, a partir de '
                                       'vídeo, cuantifique la eficiencia de la técnica de nado, detecte el inicio de la '
                                       'fatiga técnica y atribuya sus causas a variables biomecánicas.']):
        poner_texto(t.cell(fila, 1).paragraphs[0], txt)
    t = Table(b[246], doc._body)
    for fila, (valor, com) in zip(range(1, 6), [
            ('300 h · 6.000 €', 'Estimación: 12 ECTS × 25 h, valoradas a 20 €/h'),
            ('1.200 €', 'Valor aproximado de mercado del ordenador personal (800 €) y de la cámara GoPro (400 €)'),
            ('0 €', 'Software libre: Python, PyTorch, Ultralytics, OpenCV, scikit-learn, shap, Git; Google Colab gratuito'),
            ('0 €', 'Artículos de acceso abierto o a través de la biblioteca de la universidad'),
            ('0 €', 'Sin sensores ni material adicional')]):
        poner_texto(t.cell(fila, 1).paragraphs[0], valor)
        poner_texto(t.cell(fila, 2).paragraphs[0], com)
        for extra in t.cell(fila, 2).paragraphs[1:]:
            borrar(extra._p)
    for i, fila in enumerate(t.rows):                     # la tabla de presupuesto tampoco se parte
        fila._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
        for celda in fila.cells:
            for par in celda.paragraphs:
                par.paragraph_format.keep_with_next = i < len(t.rows) - 1

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
        fn(Escritor(doc, b[h], ppr_vineta))

    w = Escritor(doc, b[99], ppr_vineta)
    w.p(RESUMEN)
    w.p(f'**Palabras clave:** {PALABRAS_CLAVE}', alinear='izq')
    w = Escritor(doc, b[112], ppr_vineta)
    w.p(ABSTRACT)
    w.p(f'**Keywords:** {KEYWORDS}', alinear='izq')
    poner_texto(P(118), 'Agradezco a mi director/a su orientación durante el proyecto, al club y a los nadadores su '
                        'colaboración en las grabaciones, y a mi familia su apoyo durante el máster.')

    # índices de figuras, tablas y ecuaciones
    for h, tipo in [(165, 'Figura'), (170, 'Tabla')]:
        par = Escritor(doc, b[h], ppr_vineta).p('', alinear='izq')
        campo(par, f'TOC \\h \\z \\c "{tipo}"', 'Actualizar campos (F9) para generar el índice.')
        if tipo == 'Tabla':
            salto = copy.deepcopy(b[169]); par._p.addnext(salto)
            titulo = copy.deepcopy(b[170]); salto.addnext(titulo)
            poner_texto(Paragraph(titulo, doc._body), 'Índice de Ecuaciones')
            pe = Escritor(doc, titulo, ppr_vineta).p('', alinear='izq')
            campo(pe, 'TOC \\h \\z \\c "Ecuación"', 'Actualizar campos (F9) para generar el índice.')

    # referencias numeradas (orden de primera cita), con marcador para el enlace desde cada cita
    w = Escritor(doc, b[270], ppr_vineta)
    orden = EST['citas'] or EST['citas_pasada']
    for n, k in enumerate(orden, 1):
        par = w.p('', estilo='Bibliography', alinear='izq')
        par.paragraph_format.left_indent = Cm(1)
        par.paragraph_format.first_line_indent = Cm(-1)
        par.paragraph_format.space_after = Pt(4)
        EST['marcador'] += 1
        bs = OxmlElement('w:bookmarkStart'); bs.set(qn('w:id'), str(EST['marcador'])); bs.set(qn('w:name'), f'ref_{k}')
        be = OxmlElement('w:bookmarkEnd'); be.set(qn('w:id'), str(EST['marcador']))
        par._p.append(bs); par._p.append(_run_xml(f'[{n}]')); par._p.append(be)
        par._p.append(_run_xml('\t'))
        runs_con_formato(par, REFS[k])

    a_borrar = set(range(29, 97)) | set(range(100, 111)) | {113, 115} | set(range(119, 125)) | {127, 132} \
        | {24, 28, 97, 98} | set(range(290, 301)) | {166, 171} | {175, 176} | {192} | {207, 208} | set(range(271, 287)) | {287} | {301}
    for h, guia, fn in secciones:
        a_borrar |= set(guia)
    for i in sorted(a_borrar, reverse=True):
        borrar(b[i])

    ajustes = doc.settings.element
    uf = ajustes.find(qn('w:updateFields'))
    if uf is None:
        uf = OxmlElement('w:updateFields'); ajustes.append(uf)
    uf.set(qn('w:val'), 'true')
    return doc


def main():
    construir()
    EST['citas'] = list(EST['citas_pasada'])
    doc = construir()
    doc.save(str(SALIDA))
    print(f'Generado: {SALIDA} ({len(EST["citas"])} referencias, {EST["cont"]})')
    if shutil.which('soffice'):
        r = subprocess.run([sys.executable, str(AQUI / 'actualizar_indices.py'), str(SALIDA), str(FINAL)],
                           capture_output=True, text=True)
        print(f'Índices calculados: {FINAL}' if FINAL.exists() and r.returncode == 0 else f'No se pudieron calcular los índices: {r.stderr[-500:]}')


if __name__ == '__main__':
    main()
