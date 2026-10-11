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



# ---------------------------------------------------------------- estimación por reglas biomecánicas
# Con 11-14 vídeos reales y cada estilo nadado por 1-2 personas, un modelo entrenado aprende a reconocer a la persona
# y no el estilo (exactitud 0 % con nadadores nuevos). Las reglas se basan en la definición de cada estilo y no
# dependen de quién nade:
#   1) brazos ALTERNOS (crol, espalda) o SIMULTÁNEOS (mariposa, braza): correlación entre la señal de las dos manos.
#      De lado el modelo de pose copia en parte el brazo visible en el oculto, lo que sube la correlación: el umbral
#      lateral es más alto que el frontal.
#   2) entre los simultáneos, en braza la cabeza va más alta (respiración frontal en cada ciclo): la nariz queda por
#      encima de la línea de los hombros. Entre los alternos, en espalda la cara mira hacia arriba.
# Valores medidos en los 17 vídeos reales (ver CLAUDE.md); la regla 2 se apoya en muy pocos vídeos: orientativa.
UMBRAL_CORR = {'lateral': 0.65, 'frontal': 0.20}
UMBRAL_NARIZ_BRAZA = -0.05      # nariz respecto a los hombros, en troncos (negativo = por encima)
UMBRAL_NARIZ_ESPALDA = -0.30    # cara claramente hacia arriba


def _senales(k2d, fps, vista):
    fr = medidas.medidas_por_fotograma(k2d, fps, vista=vista)
    s = 'front' if vista == 'frontal' else 'prof2d'          # de frente: recorrido de cada muñeca (medidas.py)
    mI, mD = fr[f'munI_{s}'].to_numpy(), fr[f'munD_{s}'].to_numpy()
    hom = np.nanmean([k2d[:, LSH], k2d[:, RSH]], 0)
    cad = np.nanmean([k2d[:, LHIP], k2d[:, RHIP]], 0)
    e = hom - cad
    L = np.linalg.norm(e, axis=1)
    u = e / L[:, None]
    abajo = np.c_[-u[:, 1], u[:, 0]]
    abajo = abajo * np.where(abajo[:, 1:2] < 0, -1, 1)
    nariz = ((k2d[:, 0] - hom) * abajo).sum(1) / np.nanmedian(L)
    valido = ~np.isnan(fr.inclinacion_tronco.to_numpy()) if vista == 'lateral' else ~np.isnan(L)
    return mI, mD, np.where(valido, nariz, np.nan)


def estimar_por_reglas(k2d, fps, tramos):
    """Estilo estimado con reglas biomecánicas. tramos: [(inicio, fin, vista, ...)] (ver vista.detectar_vista).

    Devuelve dict(estilo (o None), familia 'alternos'|'simultaneos', estilo_para_ciclos, seguridad 'alta'|'media'|'baja',
    razones [texto], medidas {...}). Para contar ciclos basta la familia (2 o 1 brazadas por ciclo).
    """
    corrs, pesos, narices, vistas = [], [], [], []
    for a, b, v, *_ in tramos:
        if v not in UMBRAL_CORR or b - a < 2 * fps:
            continue
        mI, mD, nz = _senales(k2d[a:b], fps, v)
        ok = ~(np.isnan(mI) | np.isnan(mD))
        if ok.sum() < 2 * fps or np.std(mI[ok]) < 1e-9 or np.std(mD[ok]) < 1e-9:
            continue
        c = float(np.corrcoef(mI[ok], mD[ok])[0, 1])
        corrs.append(c - UMBRAL_CORR[v])                     # distancia al umbral de su vista
        pesos.append(ok.sum())
        narices.append(np.nanmedian(nz))
        vistas.append(v)
    if not corrs:
        return dict(estilo=None, familia=None, seguridad='baja', medidas={}, estilo_para_ciclos=None,
                    razones=['No hay suficiente señal de los dos brazos para estimar el estilo.'])
    margen = float(np.average(corrs, weights=pesos))
    nariz = float(np.nanmedian(narices)) if np.any(~np.isnan(narices)) else np.nan
    simult = margen >= 0
    familia = 'simultaneos' if simult else 'alternos'
    razones = [f'Correlación entre las manos {margen:+.2f} respecto al umbral de la vista ({", ".join(sorted(set(vistas)))}): '
               f'brazos {"simultáneos (mariposa o braza)" if simult else "alternos (crol o espalda)"}.']
    solo_frontal = set(vistas) == {'frontal'}
    if simult and solo_frontal:                 # de frente la altura de la cabeza no se ve bien
        estilo_ = None
        razones.append('De frente no se distingue la mariposa de la braza: indicar el estilo.')
    elif simult:
        estilo_ = 'braza' if nariz < UMBRAL_NARIZ_BRAZA else 'mariposa'
        razones.append(f'Nariz {nariz:+.2f} troncos respecto a los hombros: cabeza {"alta (braza)" if estilo_ == "braza" else "en la línea del cuerpo (mariposa)"}.')
    else:
        estilo_ = 'espalda' if nariz < UMBRAL_NARIZ_ESPALDA else 'crol'
        razones.append(f'Nariz {nariz:+.2f} troncos: cara {"hacia arriba (espalda)" if estilo_ == "espalda" else "hacia el fondo o de lado (crol)"}.')
    seguridad = 'alta' if abs(margen) >= 0.2 else 'media' if abs(margen) >= 0.08 else 'baja'
    return dict(estilo=estilo_, familia=familia, seguridad=seguridad, razones=razones,
                estilo_para_ciclos=estilo_ or ('mariposa' if simult else 'crol'),   # 1 o 2 brazadas por ciclo
                medidas=dict(margen_correlacion=round(margen, 3), nariz=round(nariz, 3) if not np.isnan(nariz) else None))
