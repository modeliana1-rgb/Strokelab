"""Reduce un vídeo (p. ej. 5K de GoPro) a 1920 píxeles de lado mayor, con los mismos fotogramas por segundo.

No se pierde información para el análisis: analizar.py ya reduce cada fotograma a 1920 px antes del modelo de pose.
Sirve para que los vídeos quepan en la cuota del clúster y se lean más rápido. Usa el ffmpeg de imageio-ffmpeg
(pip install imageio-ffmpeg), así que funciona igual en Windows y en Linux.

Uso:  python reducir_video.py <vídeo o carpeta> --salida <carpeta>      (sin audio, H.264, calidad alta: crf 18)
"""
import argparse
import subprocess
from pathlib import Path

EXT = {'.mp4', '.mov', '.m4v', '.avi', '.mkv'}


def reducir(origen, destino, lado=1920, crf=18):
    import imageio_ffmpeg
    escala = f"scale='if(gt(iw,ih),min({lado},iw),-2)':'if(gt(iw,ih),-2,min({lado},ih))'"
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-loglevel', 'error', '-stats', '-i', str(origen), '-vf', escala,
           '-c:v', 'libx264', '-preset', 'veryfast', '-crf', str(crf), '-pix_fmt', 'yuv420p', '-an', str(destino)]
    subprocess.run(cmd, check=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('origen')
    ap.add_argument('--salida', required=True)
    ap.add_argument('--lado', type=int, default=1920)
    a = ap.parse_args(argv)
    origen, salida = Path(a.origen), Path(a.salida)
    salida.mkdir(parents=True, exist_ok=True)
    videos = sorted(p for p in origen.iterdir() if p.suffix.lower() in EXT) if origen.is_dir() else [origen]
    if origen.is_dir() and (origen / 'lista_videos.csv').exists() and not (salida / 'lista_videos.csv').exists():
        import shutil
        shutil.copy(origen / 'lista_videos.csv', salida / 'lista_videos.csv')     # la lista ya revisada viaja con los vídeos
    for v in videos:
        if '_ANOTADO' in v.stem or v.stem.startswith('video_anotado'):
            continue
        dest = salida / v.name              # mismo nombre: la lista de vídeos sigue valiendo
        if dest.exists():
            print(f'ya existe, se salta: {dest.name}')
            continue
        print(f'{v.name} -> {dest}')
        reducir(v, dest, a.lado)
        print(f'   {v.stat().st_size / 1e9:.2f} GB -> {dest.stat().st_size / 1e9:.2f} GB')


if __name__ == '__main__':
    main()
