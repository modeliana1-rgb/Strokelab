"""Descarga SOLO algunos vídeos de un zip enorme de SwimXYZ en Zenodo (36-40 GB), sin bajar el zip entero.

Usa lecturas parciales (HTTP Range) con la librería remotezip: primero se lee el índice del zip y después solo los
archivos elegidos. Así bastan unos cientos de MB para tener vídeos de las vistas que interesan.

Instalar:  pip install remotezip
Uso:
  python descargar_swimxyz.py --url "<enlace del .zip en Zenodo>" --listar            (ver qué vídeos hay)
  python descargar_swimxyz.py --url "<enlace>" --filtro Front Water_Quantity_0,75 --max 24 --salida swimxyz_videos
  --filtro: todas las palabras deben aparecer en la ruta del vídeo (p. ej. la vista y la carpeta de agua).
"""
import argparse
from pathlib import Path

EXT_VIDEO = ('.mp4', '.avi', '.mov', '.mkv', '.webm')


def main(argv=None):
    from remotezip import RemoteZip
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--url', required=True)
    ap.add_argument('--listar', action='store_true')
    ap.add_argument('--filtro', nargs='*', default=[])
    ap.add_argument('--max', type=int, default=24)
    ap.add_argument('--salida', default='swimxyz_videos')
    a = ap.parse_args(argv)
    with RemoteZip(a.url) as z:
        videos = [i for i in z.infolist() if i.filename.lower().endswith(EXT_VIDEO)]
        print(f'{len(videos)} vídeos en el zip ({sum(i.file_size for i in videos) / 1e9:.1f} GB)')
        if a.listar:
            carpetas = sorted({'/'.join(i.filename.split('/')[:3]) for i in videos})
            for c in carpetas:
                n = [i for i in videos if i.filename.startswith(c)]
                print(f'  {c}: {len(n)} vídeos, {sum(i.file_size for i in n) / 1e6:.0f} MB')
            print('Ejemplo de ruta:', videos[0].filename if videos else '-')
            return 0
        elegidos = [i for i in videos if all(f.lower() in i.filename.lower() for f in a.filtro)][:a.max]
        print(f'Se descargan {len(elegidos)} vídeos ({sum(i.file_size for i in elegidos) / 1e6:.0f} MB) en {a.salida}')
        for n, i in enumerate(elegidos, 1):
            z.extract(i, a.salida)
            print(f'  [{n}/{len(elegidos)}] {i.filename}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
