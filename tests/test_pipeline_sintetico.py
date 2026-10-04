"""Prueba de extremo a extremo de la Vertical Tabular con un nadador sintético que se fatiga.

Uso:  MPLBACKEND=Agg python tests/test_pipeline_sintetico.py
"""
import os, json, numpy as np, cv2, nbformat
ROOT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..')
rng=np.random.default_rng(0)
FPS=30; T=FPS*90; W,H=640,360
t=np.arange(T)/FPS
fat=1/(1+np.exp(-(t-55)/4))           # fatiga a partir de ~55 s
period=1.35-0.25*fat                   # ciclo más rápido
phase=2*np.pi*np.cumsum(1/period)/FPS
reach=75-22*fat; elbow_bend=25+20*fat
kps=np.zeros((T,17,2)); conf=np.full((T,17),0.8)
hip=np.c_[100+1.2*t*3, np.full(T,200.)]; hip[:,0]=100+t*5*(1-0.3*fat)  # cámara fija, nadador avanza
hip[:,1]+=5*fat*np.sin(phase)          # más oscilación
sh=hip+np.c_[np.full(T,80.),-4-6*fat]
for side,(S,E,Wr,Hp,K,A),off,asym in [('L',(5,7,9,11,13,15),np.pi,1.0),('R',(6,8,10,12,14,16),0,1.0-0.25*fat)]:
    ph=phase+off; r=reach*asym
    kps[:,S]=sh; kps[:,Hp]=hip
    wr=sh+np.c_[r*np.cos(ph), 0.6*r*np.sin(ph)]
    mid=(sh+wr)/2; d=wr-sh; n=np.c_[-d[:,1],d[:,0]]/np.linalg.norm(d,axis=1)[:,None]
    kps[:,E]=mid+n*elbow_bend[:,None]; kps[:,Wr]=wr
    kps[:,K]=hip+np.c_[np.full(T,-60.),np.zeros(T)]; kps[:,A]=hip+np.c_[np.full(T,-120.),(12-5*fat)*np.sin(6*np.pi*np.cumsum(1/period)/FPS+off)]
kps[:,0]=sh+np.c_[np.full(T,30.),np.zeros(T)]; kps[:,1:5]=kps[:,[0]]
kps+=rng.normal(0,1.5,kps.shape)
drop=rng.random((T,17))<0.08; conf[drop]=0.1
conf[600:620]=0  # hueco de detección
kps[conf==0]=np.nan
# Errores reales de MoveNet bajo el agua: tronco colapsado (cadera sobre hombro) y muñecas disparadas
for t0 in (900, 1800, 2300):
    kps[t0:t0+4,[11,12]]=kps[t0:t0+4,[5,6]]+rng.normal(0,2,(4,2,2))
    kps[t0+10:t0+13,[9,10]]+=rng.normal(0,900,(3,2,2))
# Tramo inicial sin nadador en cuadro (como en el vídeo real)
conf[:150]=0.05
OUT=os.path.join(ROOT,'test_out'); os.makedirs(OUT,exist_ok=True)
np.savez(f'{OUT}/keypoints_raw.npz',kps=kps,conf=conf,fps=FPS,w=W,h=H)
vw=cv2.VideoWriter(os.path.join(OUT,'')+'synth.mp4',cv2.VideoWriter_fourcc(*'mp4v'),FPS,(W,H))
for i in range(T): vw.write(np.full((H,W,3),(120,80,20),np.uint8))
vw.release()

nb=nbformat.read(os.path.join(ROOT,'notebooks','StrokeLab_v3_pipeline.ipynb'),4)
g={'display':print,'__name__':'__main__'}
cfg=f"VIDEO_PATH='{OUT}/synth.mp4'; OUT_DIR='{OUT}'; NADADOR='Sintético'; METROS_ANCHO_ENCUADRE=8.0"
for c in nb.cells:
    if c.cell_type!='code': continue
    src=c.source
    if 'colab_only' in c.metadata.get('tags',[]):
        if 'drive.mount' in src: src=cfg
        elif 'cv2.VideoWriter' in src:
            src=src.replace('/content/anotado_tmp.mp4',os.path.join(OUT,'')+'anot.mp4').split('!ffmpeg')[0]
        else: continue
    exec(compile(src,'cell','exec'),g)
print(open(f'{OUT}/resumen_fatiga.json').read())
cap=cv2.VideoCapture(os.path.join(OUT,'')+'anot.mp4'); print('frames anotados',cap.get(7))
res=json.load(open(f'{OUT}/resumen_fatiga.json'))
# La fatiga sintética se introduce alrededor de t=55 s (sigmoide de escala 4 s)
assert res['inicio_fatiga_s'] is not None and 40 <= res['inicio_fatiga_s'] <= 60, res['inicio_fatiga_s']
assert int(cap.get(7)) == T
cic=__import__('pandas').read_csv(f'{OUT}/features_por_ciclo.csv')
assert cic[['alcance_I','alcance_D']].max().max() < 3, 'alcance imposible: no se han filtrado las detecciones absurdas'
assert cic.codo_min_I.min() > 10 and cic.codo_min_D.min() > 10, 'ángulo de codo imposible'
print('OK: test sintético superado')
