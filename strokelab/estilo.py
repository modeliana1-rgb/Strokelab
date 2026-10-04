"""Clasificación del estilo de nado (crol, espalda, mariposa, braza) con explicación SHAP.

Se trabaja por ventanas de 4 s (cada 2 s) con rasgos que NO dependen del estilo, para no usar la etiqueta al
calcularlos (el ciclo sí depende del estilo, así que no se usan variables por ciclo):
  - corr_brazos: correlación entre la señal de la mano izquierda y la derecha (+1 a la vez, -1 alternos).
  - nariz: posición de la nariz respecto a los hombros, hacia el fondo (boca abajo +, boca arriba -).
  - rodilla_p10: ángulo de rodilla más cerrado (la patada de braza lleva los talones a los glúteos).
  - tobillos_sep / corr_piernas: separación de los pies y si las piernas van juntas (delfín, rana) o alternas.
  - osc_cadera: cuánto sube y baja la cadera (ondulación de mariposa y braza).
  - periodo_mano: periodo dominante del movimiento de las manos.
Modelo: bosque aleatorio (Random Forest) con validación agrupada por vídeo (GroupKFold): las ventanas de un mismo
vídeo nunca están a la vez en entrenamiento y en prueba. SHAP (TreeSHAP) explica qué rasgo decide cada estilo.
"""
import numpy as np
import pandas as pd

from strokelab import medidas

ESTILOS = ['crol', 'espalda', 'mariposa', 'braza']
RASGOS = ['corr_brazos', 'nariz', 'rodilla_p10', 'tobillos_sep', 'corr_piernas', 'osc_cadera', 'periodo_mano', 'frontal']
NOMBRES = {'corr_brazos': 'Brazos a la vez (+) o alternos (-)', 'nariz': 'Nariz hacia el fondo (+) o arriba (-)',
           'rodilla_p10': 'Rodilla más flexionada (°)', 'tobillos_sep': 'Separación de pies',
           'corr_piernas': 'Piernas juntas (+) o alternas (-)', 'osc_cadera': 'Ondulación de la cadera',
           'periodo_mano': 'Periodo de las manos (s)', 'frontal': 'Vista frontal'}
LSH, RSH, LWR, RWR, LHIP, RHIP, LKN, RKN, LAN, RAN = 5, 6, 9, 10, 11, 12, 13, 14, 15, 16


def _corr(a, b):
    ok = ~(np.isnan(a) | np.isnan(b))
    if ok.sum() < 10 or np.std(a[ok]) < 1e-9 or np.std(b[ok]) < 1e-9:
        return np.nan
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


def _periodo(x, fps):
    ok = ~np.isnan(x)
    if ok.sum() < 2 * fps:
        return np.nan
    x = np.where(ok, x - np.nanmean(x), 0.0)
    ac = np.correlate(x, x, 'full')[len(x) - 1:]
    a, b = int(0.4 * fps), min(len(ac) - 1, int(3.0 * fps))
    if b <= a:
        return np.nan
    return (a + int(np.argmax(ac[a:b]))) / fps


def rasgos_ventanas(k2d, fps, vista='lateral', ventana=4.0, paso=2.0):
    """Rasgos por ventana a partir de los puntos 2D limpios (salida de medidas.limpiar)."""
    fr = medidas.medidas_por_fotograma(k2d, fps, vista=vista)
    frontal = vista == 'frontal'
    hom = np.nanmean([k2d[:, LSH], k2d[:, RSH]], 0)
    cad = np.nanmean([k2d[:, LHIP], k2d[:, RHIP]], 0)
    if frontal:
        escala = np.nanmedian(np.linalg.norm(k2d[:, LSH] - k2d[:, RSH], axis=1))
        abajo = np.tile([0.0, 1.0], (len(k2d), 1))
        mI, mD = fr.munI_front.to_numpy(), fr.munD_front.to_numpy()
    else:
        e = hom - cad
        L = np.linalg.norm(e, axis=1)
        escala = np.nanmedian(L)
        u = e / L[:, None]
        abajo = np.c_[-u[:, 1], u[:, 0]]
        abajo = abajo * np.where(abajo[:, 1:2] < 0, -1, 1)
        mI, mD = fr.munI_prof2d.to_numpy(), fr.munD_prof2d.to_numpy()
    nariz = ((k2d[:, 0] - hom) * abajo).sum(1) / escala
    rod = np.fmin(medidas.angulo(k2d[:, LHIP], k2d[:, LKN], k2d[:, LAN]), medidas.angulo(k2d[:, RHIP], k2d[:, RKN], k2d[:, RAN]))
    sep = np.linalg.norm(k2d[:, LAN] - k2d[:, RAN], axis=1) / escala
    pie = lambda A, H: ((k2d[:, A] - k2d[:, H]) * abajo).sum(1)
    pI, pD = pie(LAN, LHIP), pie(RAN, RHIP)
    cy = pd.Series((cad * abajo).sum(1) / escala)
    osc = (cy - cy.rolling(int(2 * fps), center=True, min_periods=5).median()).to_numpy()
    mano = np.fmax(mI, mD)
    filas = []
    n, w, s = len(k2d), int(ventana * fps), int(paso * fps)
    for a in range(0, max(1, n - w + 1), s):
        b = a + w
        if np.mean(~np.isnan(mano[a:b])) < 0.5:            # ventana sin nadador suficiente
            continue
        filas.append(dict(t_inicio_s=a / fps, corr_brazos=_corr(mI[a:b], mD[a:b]), nariz=np.nanmedian(nariz[a:b]),
                          rodilla_p10=np.nanpercentile(rod[a:b], 10) if np.any(~np.isnan(rod[a:b])) else np.nan,
                          tobillos_sep=np.nanmedian(sep[a:b]), corr_piernas=_corr(pI[a:b], pD[a:b]),
                          osc_cadera=np.nanstd(osc[a:b]), periodo_mano=_periodo(mano[a:b], fps), frontal=float(frontal)))
    return pd.DataFrame(filas, columns=['t_inicio_s'] + RASGOS)


def entrenar(X, y):
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import make_pipeline
    return make_pipeline(SimpleImputer(strategy='median'),
                         RandomForestClassifier(n_estimators=300, min_samples_leaf=2, random_state=0)).fit(X[RASGOS], y)


def evaluar(datos, n_splits=5):
    """GroupKFold por vídeo. Devuelve exactitud por ventana, por vídeo (voto) y la matriz de confusión por vídeo."""
    from sklearn.model_selection import GroupKFold
    pred = pd.Series(index=datos.index, dtype=object)
    proba = pd.DataFrame(index=datos.index, columns=ESTILOS, dtype=float)
    for tr, te in GroupKFold(n_splits=n_splits).split(datos, datos.estilo, datos.video):
        m = entrenar(datos.iloc[tr], datos.estilo.iloc[tr])
        pr = pd.DataFrame(m.predict_proba(datos.iloc[te][RASGOS]), columns=m.classes_, index=datos.index[te])
        proba.loc[pr.index, pr.columns] = pr
        pred.iloc[te] = pr.idxmax(axis=1).values
    datos = datos.assign(pred=pred, **{f'p_{e}': proba[e] for e in ESTILOS})
    vid = datos.groupby('video').agg(estilo=('estilo', 'first'), **{e: (f'p_{e}', 'mean') for e in ESTILOS})
    vid['pred'] = vid[ESTILOS].astype(float).idxmax(axis=1)
    conf = pd.crosstab(vid.estilo, vid.pred).reindex(index=ESTILOS, columns=ESTILOS, fill_value=0)
    return dict(exactitud_ventana=float((datos.pred == datos.estilo).mean()),
                exactitud_video=float((vid.pred == vid.estilo).mean()), confusion=conf, por_video=vid, ventanas=datos)


def predecir(modelo, rasgos):
    """Estilo de un vídeo: media de las probabilidades de sus ventanas."""
    p = pd.DataFrame(modelo.predict_proba(rasgos[RASGOS]), columns=modelo.classes_).mean()
    return p.idxmax(), p.round(3).to_dict()


def shap_por_estilo(modelo, X):
    """Importancia SHAP media |valor| de cada rasgo para cada estilo (tabla rasgos x estilos)."""
    import shap
    imp, rf = modelo[0], modelo[-1]
    Xi = pd.DataFrame(imp.transform(X[RASGOS]), columns=RASGOS)
    sv = shap.TreeExplainer(rf).shap_values(Xi)
    sv = np.stack(sv, -1) if isinstance(sv, list) else sv          # (n, rasgos, clases)
    return pd.DataFrame(np.abs(sv).mean(0), index=RASGOS, columns=rf.classes_)[[e for e in ESTILOS if e in rf.classes_]]
