import os
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW=os.path.join(ROOT,"raw")+"/"
import json
b=json.load(open(os.path.join(ROOT,'data','base.json'))); p=json.load(open(os.path.join(ROOT,'data','polls_post.json')))
import sys, pandas as pd, numpy as np
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from polls_model import means
m=means(p['post'],b)
import regional
b_reg,reg_log=regional.adjust(b,m,p['date'])
MESES='enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()
fes=lambda d:f"{d.day} de {MESES[d.month-1]} de {d.year}"
last=pd.Timestamp(p['last_poll']); asof=pd.Timestamp(p['date']); days=int((pd.Timestamp('2026-11-29')-last).days)
HZ=[(3,2.19),(7,2.25),(14,2.23),(21,2.31),(30,2.90),(45,2.88),(60,4.03),(90,4.80)]
err=round(float(np.interp(min(days,90),[h for h,_ in HZ],[e for _,e in HZ])),1)
tsf=os.path.join(ROOT,'data','timeseries.json'); ts=json.load(open(tsf)) if os.path.exists(tsf) else None

# --- puntos de encuestas individuales para la sección de evolución (mismas transformaciones que la media) ---
def poll_points(b,ts):
    from polls_model import load_polls, house_correct
    P=house_correct(load_polls()); P=P[P.end>=pd.Timestamp('2026-01-01')]
    tw=[(pd.Timestamp(w['date']),w) for w in ts['weeks']] if ts else []
    def wk(d):
        return min(tw,key=lambda x:abs((x[0]-d).days))[1] if tw else None
    fr={(t['from'],t['to']):t['frac'] for t in b['transfers']}
    out=[]
    for r in P.itertuples(index=False):
        g=lambda k:getattr(r,k,None) if k in P.columns and pd.notna(getattr(r,k,None)) else None
        v={}
        for k in ['PSOE','Vox','SALF','ERC','Junts','EH Bildu','PNV','BNG','CC','AA']:
            x=g(k)
            if x is not None: v[k]=float(x)
        if g('PP') is not None: v['PP']=float(g('PP'))+(g('UPN') or 0)
        pod=g('Podemos'); se=g('SUMESP'); fv=g('FVobs')
        if pod is not None:
            v['Podemos']=pod*(1-fr.get(('Podemos','ERC'),0)-fr.get(('Podemos','FV'),0)-fr.get(('Podemos','FA'),0))
            if 'ERC' in v: v['ERC']+=pod*fr.get(('Podemos','ERC'),0)
        if se is not None:
            fvv=fv if fv is not None else 1.0
            fa=se-fvv+b['nc_nat']*100
            v['FA']=fa*(1-fr.get(('FA','FV'),0)-fr.get(('FA','Otros'),0))+(pod or 0)*fr.get(('Podemos','FA'),0)
            if fv is not None: v['FV']=fv+fa*fr.get(('FA','FV'),0)+(pod or 0)*fr.get(('Podemos','FV'),0)
        w=wk(r.mid)
        def bloc(keys):
            if not all(k in v for k in keys[:2]): return None
            return round(sum(v.get(k, w['parties'][k]['vote'] if w and k in w['parties'] else 0) for k in keys),2)
        bl={'R':bloc(['PP','Vox','SALF']),'L':bloc(['PSOE','FA','FV','Podemos'])}
        if bl['R'] is not None and bl['L'] is not None: bl['O']=None
        out.append(dict(d=str(r.mid.date()),f=r.firm,v={k:round(x,2) for k,x in v.items()},b={k:x for k,x in bl.items() if x is not None}))
    return out
pts=poll_points(b,ts)
print({k:v['mean'] for k,v in m.items()})
D={'means':m,'parties':b['parties'],'provinces':b_reg['provinces'],'regional':[dict(ccaa=e['ccaa'],polls=e['polls']) for e in reg_log],'assumptions':b['assumptions'],'post':p['post'],
   'meta':{'poll_date':fes(last),'window_from':fes(asof-pd.Timedelta(days=p['window_days'])),'half_life':p['half_life'],'n_polls':p['n_polls'],'firms':p['firms'],'built':fes(pd.Timestamp.now()),'poll_days':days,'err_default':err},'ts':ts,'pts':pts}
s=open(os.path.join(ROOT,'model','template.html')).read().replace('__DATA__',json.dumps(D,ensure_ascii=False).replace('</','<\\/'))
HEAD='''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="description" content="Simulador bayesiano de escaños del Congreso para las generales del 29 de noviembre de 2026: media de encuestas, sensibilidad por partido y voto útil por provincia.">
<meta property="og:title" content="Voto útil a la derecha"><meta property="og:description" content="Mueve los votos y mira dónde rinde el voto a cada partido, provincia a provincia.">
<meta property="og:type" content="website"><meta property="og:image" content="__SITE__docs/portada.png"><meta property="og:url" content="__SITE__">
<meta name="twitter:card" content="summary_large_image"><style>:root{padding-top:env(safe-area-inset-top);padding-bottom:env(safe-area-inset-bottom)}body{margin:0;font-size:14px}img{max-width:100%}[hidden]{display:none!important}</style></head><body>
'''
SITE=os.environ.get('SITE_URL','')
open(os.path.join(ROOT,'index.html'),'w').write(HEAD.replace('__SITE__',SITE)+s+'\n</body></html>\n')
json.dump(D,open(os.path.join(ROOT,'data','page_data.json'),'w'),ensure_ascii=False)
print(len(s))
