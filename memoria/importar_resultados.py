"""Copia a memoria/datos_reales lo que la memoria necesita de una carpeta de resultados de lote.py o de su
para_claude.zip: resúmenes, variables por ciclo, explicaciones y figuras de fatiga (no los puntos ni los vídeos).

Uso:  python memoria/importar_resultados.py <para_claude.zip | carpeta de resultados>
"""
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

DESTINO = Path(__file__).resolve().parent / 'datos_reales'
UTILES = {'resumen_lote.csv', 'resumen_sesiones.csv', 'resumen.json', 'variables_por_ciclo.csv', 'resumen_sesion.json',
          'variables_por_ciclo_sesion.csv', 'fig_fatiga_timeline.png', 'fig_shap_summary.png',
          'fig_shap_waterfall_inicio.png', 'fig_ciclos.png', 'shap_por_ciclo.csv'}


def main(origen):
    origen = Path(origen)
    tmp = None
    if origen.suffix.lower() == '.zip':
        tmp = Path(tempfile.mkdtemp())
        with zipfile.ZipFile(origen) as z:
            z.extractall(tmp)
        raices = [p.parent for p in tmp.rglob('resumen_lote.csv')]
        if not raices:
            sys.exit('El zip no contiene resumen_lote.csv')
        origen = raices[0]
    if DESTINO.exists():
        shutil.rmtree(DESTINO)
    n = 0
    for p in origen.rglob('*'):
        if p.is_file() and p.name in UTILES:
            d = DESTINO / p.relative_to(origen)
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(p, d)
            n += 1
    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f'{n} archivos copiados a {DESTINO}')


if __name__ == '__main__':
    main(sys.argv[1])
