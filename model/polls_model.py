"""Agregación bayesiana de encuestas (modelo normal de efectos aleatorios con caída temporal).

aggregate(asof) devuelve la media de encuestas a una fecha; means(post, base) la traduce a las
candidaturas reales del 29-N. Ejecutado como script, escribe data/polls_post.json para la última fecha.
"""
import os, sys, json
import pandas as pd, numpy as np
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WINDOW=45; HALF=21; PRIOR_SD=5.0
PRIOR={'PP':33.1,'PSOE':31.7,'Vox':12.4,'SUMESP':7.5,'Podemos':3.3,'SALF':2.0,'ERC':1.9,'Junts':1.6,'EH Bildu':1.4,'PNV':1.1,
       'BNG':0.6,'CC':0.5,'UPN':0.2,'AA':0.5,'AC':0.6,'FVobs':1.0}
PARTY_FIRMS={'PSOE','PP','Vox','Sumar','Podemos','SocioMétrica/PP'}

def load_polls():
    P=pd.read_csv(os.path.join(ROOT,'data','polls_2026.csv'),parse_dates=['end'])
    # fuera las encuestas encargadas o publicadas por partidos (p. ej. «Vox/The Objective», «SocioMétrica/PP»)
    PARTIES={'PSOE','PP','Vox','Sumar','Podemos','SALF','ERC','Junts','PNV','EH Bildu','BNG','CC','UPN','Compromís','Más Madrid','IU'}
    party=P.firm.fillna('').map(lambda f:f in PARTY_FIRMS or any(x.strip() in PARTIES for x in f.split('/')))
    P=P[P.PP.notna()&P.end.notna()&~party].copy()
    comb=P.get('FAFV_comb',pd.Series(False,index=P.index)).fillna(False).astype(bool)
    # FA+FV como "espacio Sumar" en todas las encuestas
    P['SUMESP']=np.where(P.table==0,np.where(comb,P.FA,P.FA+P.FV),P.Sumar)
    P['FVobs']=np.where(P.table==0,np.where(comb,np.nan,P.FV),P.get('FV_note'))
    return P

def aggregate(P,asof):
    asof=pd.Timestamp(asof)
    d0=P[(P.end<=asof)&(P.end>=asof-pd.Timedelta(days=WINDOW))].copy()
    # una encuesta por empresa (la más reciente) para no sobreponderar trackers
    d0=d0.sort_values('end',ascending=False).drop_duplicates('firm')
    d0['n']=d0.n.fillna(1000).clip(upper=3000)
    d0['w']=0.5**((asof-d0.end).dt.days/HALF)
    out={}
    for p,m0 in PRIOR.items():
        d=d0[d0[p].notna()] if p in d0 else d0.iloc[:0]
        if len(d)==0:
            out[p]=dict(mean=m0 if p!='AC' else 1.1,sd=0.4 if p=='AC' else PRIOR_SD*0.2,tau=None,k=0); continue
        y=d[p].values/100; n=d.n.values; w=d.w.values
        th=np.average(y,weights=w); s2=th*(1-th)/n
        # varianza entre encuestas (efectos de casa) por método de momentos
        tau2=max(np.average((y-th)**2,weights=w)-np.average(s2,weights=w),0) if len(d)>2 else (0.3*th)**2
        v=s2+tau2
        prec=np.sum(w/v)/(np.sum(w)/len(w))*(np.sum(w)**2/np.sum(w**2))/len(w)  # precisión efectiva con pesos temporales
        pm=(m0/100)/((PRIOR_SD/100)**2); pp=1/((PRIOR_SD/100)**2)
        mean=(pm+np.sum(w*y/v)/np.sum(w/v)*prec)/(pp+prec); sd=np.sqrt(1/(pp+prec))
        out[p]=dict(mean=round(mean*100,3),sd=round(sd*100,3),tau=round(np.sqrt(tau2)*100,3),k=int(len(d)))
    return dict(date=str(asof.date()),window_days=WINDOW,half_life=HALF,n_polls=int(len(d0)),firms=d0.firm.tolist(),
                last_poll=str(d0.end.max().date()) if len(d0) else None,post=out)

def means(post,b):
    """Media nacional por candidatura real del 29-N (UPN con PP, Podemos dentro de ERC/Compromís/UPC, etc.)."""
    po=post
    m={k:dict(mean=v['mean'],sd=v['sd']) for k,v in po.items() if k not in('SUMESP','FVobs','AC','UPN')}
    m['FV']=dict(mean=po['FVobs']['mean'],sd=po['FVobs']['sd'])
    m['FA']=dict(mean=po['SUMESP']['mean']-po['FVobs']['mean']+b['nc_nat']*100,sd=po['SUMESP']['sd'])
    m['PP']['mean']+=po['UPN']['mean']
    src={k:m[k]['mean'] for k in m}
    for t in b['transfers']:
        x=src[t['from']]*t['frac']; m[t['from']]['mean']-=x
        if t['to'] in m: m[t['to']]['mean']+=x
    m['Existe']=dict(mean=b['base_nat']['Existe']*100,sd=0.03)
    for k in m: m[k]['mean']=round(m[k]['mean'],2)
    return m

if __name__=='__main__':
    P=load_polls()
    asof=sys.argv[1] if len(sys.argv)>1 else str(P.end.max().date())
    r=aggregate(P,asof)
    print(r['date'],r['n_polls'],'encuestas'); print(pd.DataFrame(r['post']).T.to_string())
    json.dump(r,open(os.path.join(ROOT,'data','polls_post.json'),'w'),ensure_ascii=False)
