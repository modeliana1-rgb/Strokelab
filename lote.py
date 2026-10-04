"""StrokeLab · análisis por lotes: todos los vídeos de una carpeta, y después la fatiga por sesión.

Pasos (PowerShell, desde la carpeta del proyecto):
  1) python lote.py --carpeta C:\\Users\\user\\StrokeLab\\videos --crear-lista
     Crea videos\\lista_videos.csv con nadador, estilo, vista y sesión de cada vídeo. Revísala en Excel:
     - vista: lateral (cámara de lado), frontal (viene hacia la cámara o desde el borde) u otra (oblicua).
     - sesion: los vídeos con el mismo nombre de sesión se unen en orden para analizar la fatiga.
     - incluir: si / no.
  2) python lote.py --carpeta C:\\Users\\user\\StrokeLab\\videos
     Analiza los vídeos que falten. Si se corta, se vuelve a lanzar y continúa donde iba.

Salida en ..\\resultados: una carpeta por vídeo, una por sesión, resumen_lote.csv, resumen_sesiones.csv, lote.log
y para_claude.zip (todo menos los vídeos, para subirlo a Drive).
"""
import argparse
import csv
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
EXTENSIONES = {'.mp4', '.mov', '.avi', '.mkv', '.m4v'}
ESTILOS = ['crol', 'espalda', 'mariposa', 'braza']
COLUMNAS = ['archivo', 'nadador', 'estilo', 'vista', 'sesion', 'incluir', 'notas']

# Lo que sabemos de los vídeos de Diana (nombre en Drive). El resto sale como "?" para completarlo a mano.
CONOCIDOS = {
    'GX011614': ('Aaron', 'crol'), 'GX011617': ('Aaron', 'crol'), 'GX011618': ('Aaron', 'crol'),
    'IMG_7207': ('Aaron', 'crol'), 'IMG_7215': ('Aaron', 'crol'),
    'GX011610': ('Aaron', 'mariposa'), 'IMG_7209': ('Aaron', 'mariposa'),
    'GX011608': ('Alvaro', 'crol'), 'IMG_7205': ('Alvaro', 'espalda'),
    'GX011609': ('Lucia', 'crol'), 'GX010724': ('Lucia', 'mariposa'), 'GX010725': ('Lucia', 'mariposa'),
    'IMG_7204': ('Lucia', 'mariposa'),
    'GX011611': ('Angel', 'braza'), 'GX011616': ('Angel', 'braza'), 'IMG_7213': ('Angel', 'braza'),
    'IMG_7217': ('Angel', 'braza'),
    'GX011615': ('Nadador A', 'crol'),
}


def videos_de(carpeta):
    return sorted(p for p in carpeta.iterdir() if p.suffix.lower() in EXTENSIONES)


def crear_lista(carpeta, lista):
    previas = {f['archivo']: f for f in leer_lista(lista)} if lista.exists() else {}
    filas = []
    for v in videos_de(carpeta):
        if v.name in previas:                    # no se pisa lo que Diana ya haya corregido
            filas.append(previas[v.name])
            continue
        nadador, estilo = CONOCIDOS.get(v.stem.upper(), ('?', 'crol'))
        camara = 'gopro' if v.stem.upper().startswith('GX') else 'movil'
        filas.append(dict(archivo=v.name, nadador=nadador, estilo=estilo, vista='lateral',
                          sesion=f'{nadador}_{estilo}_{camara}', incluir='si',
                          notas='' if nadador != '?' else 'completar nadador y estilo'))
    with open(lista, 'w', newline='', encoding='utf-8-sig') as f:   # utf-8-sig: Excel lee bien las tildes
        w = csv.DictWriter(f, fieldnames=COLUMNAS, delimiter=';')
        w.writeheader()
        w.writerows(filas)
    print(f'Lista creada: {lista} ({len(filas)} vídeos). Revisa sobre todo "vista" y los "?".')
    for f in filas:
        print(f"  {f['archivo']:<16} {f['nadador']:<10} {f['estilo']:<9} {f['vista']:<8} {f['sesion']}")


def leer_lista(lista):
    with open(lista, encoding='utf-8-sig') as f:
        texto = f.read()
    sep = ';' if texto.count(';') >= texto.count(',') else ','     # Excel en español guarda con ";"
    return [{k.strip(): (v or '').strip() for k, v in fila.items() if k} for fila in csv.DictReader(texto.splitlines(), delimiter=sep)]


def duracion_s(video):
    try:
        import cv2
        cap = cv2.VideoCapture(str(video))
        n, fps = cap.get(cv2.CAP_PROP_FRAME_COUNT), cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        return n / fps if fps else 0.0
    except Exception:
        return 0.0


def ejecutar(cmd, log):
    """Lanza un paso en un proceso aparte (si falla, el lote sigue) y copia su salida a pantalla y al log."""
    with subprocess.Popen(cmd, cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                          encoding='utf-8', errors='replace', env={**__import__('os').environ, 'PYTHONIOENCODING': 'utf-8'}) as p:
        for linea in p.stdout:
            print(linea, end='')
            log.write(linea)
        log.flush()
        return p.wait()


def main(argv=None):
    ap = argparse.ArgumentParser(description='Analiza todos los vídeos de una carpeta y la fatiga por sesión.')
    ap.add_argument('--carpeta', required=True, help='carpeta con los vídeos')
    ap.add_argument('--resultados', help='carpeta de resultados (por defecto, "resultados" junto a la de vídeos)')
    ap.add_argument('--lista', help='lista de vídeos (por defecto <carpeta>/lista_videos.csv)')
    ap.add_argument('--crear-lista', action='store_true', help='solo crear o completar la lista de vídeos')
    ap.add_argument('--con-video', action='store_true', help='generar también el vídeo anotado (tarda unas 4× la duración)')
    ap.add_argument('--rehacer', action='store_true', help='repetir el análisis aunque ya exista (reutiliza la pose)')
    ap.add_argument('--solo', nargs='*', help='analizar solo estos archivos de la lista')
    ap.add_argument('--imgsz', type=int, default=640, help='YOLO: 1280 detecta mejor nadadores pequeños (~4x más lento)')
    ap.add_argument('--conf-det', type=float, default=0.25, help='YOLO: confianza mínima de la detección')
    ap.add_argument('--rehacer-pose', action='store_true', help='volver a extraer la pose aunque ya exista (p. ej. con otro --imgsz)')
    a = ap.parse_args(argv)

    carpeta = Path(a.carpeta)
    lista = Path(a.lista) if a.lista else carpeta / 'lista_videos.csv'
    if a.crear_lista or not lista.exists():
        crear_lista(carpeta, lista)
        if not a.crear_lista:
            print('\nRevisa la lista y vuelve a lanzar el mismo comando sin --crear-lista.')
        return 0

    res_dir = Path(a.resultados) if a.resultados else carpeta.parent / 'resultados'
    res_dir.mkdir(parents=True, exist_ok=True)
    filas = [f for f in leer_lista(lista) if f.get('incluir', 'si').lower() in ('si', 'sí', 's', '1', 'x')]
    if a.solo:
        filas = [f for f in filas if f['archivo'] in a.solo]
    malos = [f['archivo'] for f in filas if f.get('estilo') not in ESTILOS or f.get('vista') not in ('lateral', 'frontal', 'otra')]
    if malos:
        print(f'Corrige estilo ({"/".join(ESTILOS)}) o vista (lateral/frontal/otra) en: {", ".join(malos)}')
        return 1

    pendientes = []
    for f in filas:
        out = res_dir / Path(f['archivo']).stem
        r = out / 'resumen.json'
        hecho = r.exists() and json.loads(r.read_text(encoding='utf-8')).get('estilo') == f['estilo'] \
            and json.loads(r.read_text(encoding='utf-8')).get('vista') == f['vista']
        if a.rehacer or a.rehacer_pose or not hecho:
            pendientes.append(f)
    total = sum(duracion_s(carpeta / f['archivo']) for f in pendientes
                if a.rehacer_pose or not (res_dir / Path(f['archivo']).stem / 'keypoints_raw.npz').exists())
    print(f'{len(filas)} vídeos en la lista; {len(pendientes)} por analizar. Vídeo nuevo por procesar: {total / 60:.1f} min '
          f'-> unas {(7 if a.imgsz <= 640 else 25) * total / 3600 + 0.1 * len(pendientes):.1f} h en CPU{" (+ vídeo anotado)" if a.con_video else ""}.')

    with open(res_dir / 'lote.log', 'a', encoding='utf-8') as log:
        log.write(f'\n===== lote {time.strftime("%Y-%m-%d %H:%M")} =====\n')
        for n, f in enumerate(pendientes, 1):
            video, out = carpeta / f['archivo'], res_dir / Path(f['archivo']).stem
            if not video.exists():
                print(f'NO EXISTE: {video}')
                continue
            print(f'\n######## [{n}/{len(pendientes)}] {f["archivo"]} · {f["nadador"]} · {f["estilo"]} · vista {f["vista"]}')
            cmd = [sys.executable, str(RAIZ / 'analizar.py'), str(video), '--salida', str(out), '--nadador', f['nadador'],
                   '--estilo', f['estilo'], '--vista', f['vista'], '--imgsz', str(a.imgsz), '--conf-det', str(a.conf_det)]
            if (out / 'keypoints_raw.npz').exists() and not a.rehacer_pose:
                cmd.append('--desde-keypoints')                 # la pose ya está extraída: solo se rehace el análisis
            if not a.con_video:
                cmd.append('--sin-video')
            t0 = time.time()
            codigo = ejecutar(cmd, log)
            print(f'######## {f["archivo"]}: {"OK" if codigo == 0 else f"ERROR (código {codigo}), se sigue con el siguiente"} '
                  f'en {(time.time() - t0) / 60:.1f} min')

        # resumen por vídeo
        tabla = []
        for f in filas:
            r = res_dir / Path(f['archivo']).stem / 'resumen.json'
            d = json.loads(r.read_text(encoding='utf-8')) if r.exists() else {}
            tabla.append(dict(archivo=f['archivo'], nadador=f['nadador'], estilo=f['estilo'], vista=f['vista'], sesion=f['sesion'],
                              estado='ok' if d else 'sin resultado', duracion_s=d.get('duracion_s'),
                              pct_deteccion=d.get('pct_deteccion'), s_analizable=d.get('s_analizable'),
                              ciclos_validos=d.get('ciclos_validos'), SR_media=d.get('SR_media'),
                              inicio_fatiga_s=d.get('inicio_fatiga_s')))
        escribir(res_dir / 'resumen_lote.csv', tabla)

        # fatiga por sesión (vídeos con el mismo nombre de sesión, en el orden de la lista)
        sesiones = {}
        for f in tabla:
            if f['estado'] == 'ok':
                sesiones.setdefault(f['sesion'], []).append(f)
        tabla_s = []
        for nombre, vids in sesiones.items():
            fila = dict(sesion=nombre, nadador=vids[0]['nadador'], estilo=vids[0]['estilo'], videos=len(vids),
                        ciclos=sum(v['ciclos_validos'] or 0 for v in vids))
            if len(vids) >= 2:
                print(f'\n######## Sesión {nombre}: {", ".join(v["archivo"] for v in vids)}')
                out_s = res_dir / f'sesion_{nombre}'
                ejecutar([sys.executable, str(RAIZ / 'sesion.py'), *[str(res_dir / Path(v['archivo']).stem) for v in vids],
                          '--nadador', vids[0]['nadador'], '--salida', str(out_s)], log)
                r = out_s / 'resumen_sesion.json'
                if r.exists():
                    d = json.loads(r.read_text(encoding='utf-8'))
                    fila.update(inicio_fatiga_ciclo=d.get('inicio_fatiga_ciclo'), inicio_fatiga_pasada=d.get('inicio_fatiga_pasada'),
                                explicacion=' | '.join(d.get('explicacion', [])))
            else:
                fila.update(explicacion='un solo vídeo: ver su carpeta')
            tabla_s.append(fila)
        escribir(res_dir / 'resumen_sesiones.csv', tabla_s)

    # paquete para compartir (sin vídeos)
    with zipfile.ZipFile(res_dir / 'para_claude.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for p in res_dir.rglob('*'):
            if p.is_file() and p.suffix.lower() not in EXTENSIONES and p.name != 'para_claude.zip':
                z.write(p, p.relative_to(res_dir))
    print(f'\nResumen por vídeo: {res_dir / "resumen_lote.csv"}')
    print(f'Resumen por sesión: {res_dir / "resumen_sesiones.csv"}')
    print(f'Para compartir (sube este archivo a Drive): {res_dir / "para_claude.zip"}')
    return 0


def escribir(ruta, filas):
    if not filas:
        return
    cols = list(dict.fromkeys(k for f in filas for k in f))
    with open(ruta, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter=';')
        w.writeheader()
        w.writerows(filas)


if __name__ == '__main__':
    sys.exit(main())
