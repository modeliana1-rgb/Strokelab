"""Comprueba qué librerías de StrokeLab funcionan en este ordenador (útil con AppLocker / políticas de empresa).

Uso:  python diagnostico.py
"""
import importlib
import platform
import sys
import time

print(f'Python {sys.version.split()[0]} · {platform.system()} {platform.release()} · {platform.machine()}\n')

PRUEBAS = [
    ('numpy', 'cálculo básico'),
    ('pandas', 'tablas'),
    ('scipy', 'detección de ciclos'),
    ('sklearn', 'Isolation Forest'),
    ('cv2', 'lectura y escritura de vídeo (OpenCV)'),
    ('matplotlib', 'gráficas'),
    ('shap', 'explicabilidad'),
    ('torch', 'YOLO y MotionBERT (PyTorch)'),
    ('ultralytics', 'YOLO-Pose'),
    ('mediapipe', 'alternativa de pose sin TensorFlow'),
    ('tensorflow', 'MoveNet'),
    ('huggingface_hub', 'descarga del modelo de MotionBERT'),
]

ok = {}
for mod, para in PRUEBAS:
    t0 = time.time()
    try:
        m = importlib.import_module(mod)
        ok[mod] = True
        print(f'  OK     {mod:<12} {getattr(m, "__version__", ""):<12} {para}')
    except Exception as e:  # ImportError, DLL bloqueada por AppLocker, etc.
        ok[mod] = False
        msg = str(e).splitlines()[0][:90]
        print(f'  FALLA  {mod:<12} {"":<12} {para}  ->  {type(e).__name__}: {msg}')

if ok.get('torch'):
    import torch
    t0 = time.time(); a = torch.randn(512, 512)
    for _ in range(20): a = a @ a / 512
    print(f'\nPyTorch funciona en CPU ({time.time() - t0:.2f} s en la prueba de cálculo; hilos: {torch.get_num_threads()})')

print('\nResumen:')
print('  YOLO (recomendado)  :', 'disponible' if ok.get('torch') and ok.get('ultralytics') else 'NO disponible')
print('  MotionBERT (3D)     :', 'disponible' if ok.get('torch') else 'NO disponible')
print('  MediaPipe           :', 'disponible' if ok.get('mediapipe') else 'NO disponible')
print('  MoveNet             :', 'disponible' if ok.get('tensorflow') else 'NO disponible')
print('\nCopia todo este texto y pégaselo a Claude.')
