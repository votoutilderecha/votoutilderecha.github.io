"""Ajuste del perfil territorial con encuestas regionales (Cataluña, Galicia...).

Para cada comunidad con encuestas, el punto de partida es la proyección del modelo nacional en esa comunidad
(swing proporcional desde 2023). Se combina con las encuestas regionales como una media bayesiana ponderada
por tamaño de muestra y antigüedad: la proyección pesa como una muestra de N0 entrevistas. El cociente
posterior/proyección se aplica al perfil base de las provincias de la comunidad. Después el motor reescala
como siempre para cuadrar con la media nacional, así que la encuesta regional mueve el reparto
entre comunidades, no el total nacional.

Supuestos: los porcentajes publicados con horquilla se toman en su punto medio; si la ficha no da muestra
o fechas se supone una muestra de 600 y un campo de cinco días antes de la publicación (ver data/regional_polls.csv).
"""
import os, json, copy
import numpy as np, pandas as pd
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N0=400          # peso de la proyección del modelo en la comunidad, en entrevistas equivalentes
NCAP=1000       # tope de muestra efectiva de una encuesta regional (efectos de casa, muestras pequeñas)
WINDOW=75       # días de ventana (hay pocas encuestas regionales)
HALF=21         # vida media de la ponderación por antigüedad, igual que la nacional

def load():
    f=os.path.join(ROOT,'data','regional_polls.csv')
    if not os.path.exists(f): return pd.DataFrame()
    R=pd.read_csv(f,parse_dates=['start','end']); R['mid']=R.start+(R.end-R.start)/2
    return R

def central(B,V,base_nat,mu,iters=5):
    """Proyección central por provincia (misma lógica de reescalado que el motor de la página)."""
    f=mu/np.maximum(base_nat,1e-12); Vt=V.sum()
    for it in range(iters):
        x=B*f; x=x/x.sum(1,keepdims=True)
        if it<iters-1:
            nat=(x*V[:,None]).sum(0)/Vt; f=f*mu/np.maximum(nat,1e-9)
    return x

def adjust(b,means,asof,verbose=False):
    """Devuelve una copia de base.json con el perfil de las comunidades con encuestas regionales ajustado."""
    R=load(); asof=pd.Timestamp(asof)
    if R.empty: return b,[]
    R=R[(R.end<=asof)&(R.mid>=asof-pd.Timedelta(days=WINDOW))]
    if R.empty: return b,[]
    P=b['parties']; prov=b['provinces']
    B=np.array([[pr[p] for p in P] for pr in prov]); V=np.array([pr['valid'] for pr in prov],float)
    base_nat=(B*V[:,None]).sum(0)/V.sum()
    mu=np.array([means[p]['mean']/100 if p in means else 0 for p in P]); mu[P.index('Otros')]=max(1-mu.sum(),0.005); mu=mu/mu.sum()
    X=central(B,V,base_nat,mu); B2=B.copy(); log=[]
    for cc,G in R.groupby('ccaa'):
        idx=[k for k,pr in enumerate(prov) if pr['ccaa']==cc]
        if not idx: continue
        m=(X[idx]*V[idx,None]).sum(0)/V[idx].sum()
        w=(G.n.fillna(600).clip(upper=NCAP)*0.5**(((asof-G.mid).dt.days.clip(lower=0))/HALF)).values
        post=m.copy(); S=[]
        for j,p in enumerate(P):
            if p not in G or G[p].isna().all(): continue
            ok=G[p].notna().values
            post[j]=(N0*m[j]+np.sum(w[ok]*G[p].values[ok]/100))/(N0+np.sum(w[ok])); S.append(j)
        rest=[j for j in range(len(P)) if j not in S]
        sr=1-post[S].sum(); mr=m[rest].sum()
        for j in rest: post[j]=m[j]*sr/mr if mr>0 else m[j]
        fac=post/np.maximum(m,1e-9)
        B2[idx]=B2[idx]*fac; B2[idx]=B2[idx]/B2[idx].sum(1,keepdims=True)
        log.append(dict(ccaa=cc,polls=G.firm.tolist(),model={P[j]:round(m[j]*100,1) for j in S},poll={P[j]:round(float(np.average(G[P[j]].dropna(),weights=w[G[P[j]].notna().values]))) if False else None for j in S},post={P[j]:round(post[j]*100,1) for j in S}))
    out=copy.deepcopy(b)
    for k,pr in enumerate(out['provinces']):
        for j,p in enumerate(P): pr[p]=round(float(B2[k,j]),6)
    if verbose:
        X2=central(B2,V,(B2*V[:,None]).sum(0)/V.sum(),mu)
        for e in log:
            idx=[k for k,pr in enumerate(prov) if pr['ccaa']==e['ccaa']]
            after=(X2[idx]*V[idx,None]).sum(0)/V[idx].sum()
            e['after']={p:round(after[P.index(p)]*100,1) for p in e['post']}
            print(e['ccaa'],e['polls'],'\n  modelo',e['model'],'\n  objetivo',e['post'],'\n  tras reescalar',e['after'])
    return out,log
