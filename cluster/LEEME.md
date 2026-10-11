# StrokeLab en el clúster de la escuela (Slurm + GPU)

1. Portátil (PowerShell): reducir los vídeos 5K a 1920 px para que quepan en la cuota de 20 GB
   `pip install imageio-ffmpeg` y `python reducir_video.py C:\Users\user\StrokeLab\videos --salida C:\Users\user\StrokeLab\videos_1920`
2. Conectar la VPN y copiar código y vídeos (sustituir USUARIO y SERVIDOR):
   `scp -r C:\Users\user\StrokeLab\strokelab USUARIO@SERVIDOR:~/strokelab`
   `scp -r C:\Users\user\StrokeLab\videos_1920 USUARIO@SERVIDOR:~/videos`
3. En el clúster: `ssh USUARIO@SERVIDOR`, `cd ~/strokelab`, `bash cluster/instalar.sh`
4. Probar la GPU: `sbatch cluster/prueba_gpu.sbatch` y luego `cat prueba_gpu_*.log` (debe decir «GPU disponible»)
5. Lista de vídeos (la del portátil viaja copiada): `source venv/bin/activate`, `python3 lote.py --carpeta ../videos --crear-lista` (añade los vídeos nuevos) y completar con `nano ../videos/lista_videos.csv`
6. Lanzar: `sbatch cluster/lote.sbatch`; avance: `tail -f lote_*.log`; cola: `squeue -u $USER`
7. Traer los resultados al portátil: `scp USUARIO@SERVIDOR:~/resultados/para_claude.zip .`
