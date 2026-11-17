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

MON={m:i+1 for i,m in enumerate('Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split())}
def start_date(txt,end):
    """Primer día de campo a partir de textos como «26 Oct–15 Nov», «10–15 Nov», «12 Nov» o «27 Dec–3 Jan»."""
    import re
    if pd.isna(end): return pd.NaT
    a=str(txt).split('–')[0].strip()
    m=re.match(r'(\d+)(?:\s+([A-Z][a-z]{2}))?',a)
    if not m: return end
    mon=MON.get(m.group(2),end.month) if m.group(2) else end.month
    d=pd.Timestamp(end.year,mon,int(m.group(1)))
    if d>end: d=pd.Timestamp(end.year-1,mon,int(m.group(1)))
    return d
def load_polls():
    P=pd.read_csv(os.path.join(ROOT,'data','polls_2026.csv'),parse_dates=['end'])
    # fuera las encuestas encargadas o publicadas por partidos (p. ej. «Vox/The Objective», «SocioMétrica/PP»)
    PARTIES={'PSOE','PP','Vox','Sumar','Podemos','SALF','ERC','Junts','PNV','EH Bildu','BNG','CC','UPN','Compromís','Más Madrid','IU'}
    party=P.firm.fillna('').map(lambda f:f in PARTY_FIRMS or any(x.strip() in PARTIES for x in f.split('/')))
    P=P[P.PP.notna()&P.end.notna()&~party].copy()
    # el CIS publica con distintas empresas de campo: cuenta como una sola casa
    P['firm']=P.firm.where(~P.firm.str.startswith('CIS'),'CIS')
    # fecha efectiva = punto medio del trabajo de campo (los trackings acumulados no son «de hoy»)
    P['start']=[start_date(t,e) for t,e in zip(P.date,P.end)]
    P['mid']=P.start+(P.end-P.start)/2
    comb=P.get('FAFV_comb',pd.Series(False,index=P.index)).fillna(False).astype(bool)
    # FA+FV como "espacio Sumar" en todas las encuestas
    P['SUMESP']=np.where(P.table==0,np.where(comb,P.FA,P.FA+P.FV),P.Sumar)
    P['FVobs']=np.where(P.table==0,np.where(comb,np.nan,P.FV),P.get('FV_note'))
    return P

def aggregate(P,asof):
    asof=pd.Timestamp(asof)
    d0=P[(P.end<=asof)&(P.mid>=asof-pd.Timedelta(days=WINDOW))].copy()
    # una encuesta por empresa (la última publicada) para no contar varias veces las mismas entrevistas de un tracking
    d0=d0.sort_values('end',ascending=False).drop_duplicates('firm')
    d0['n']=d0.n.fillna(1000).clip(upper=3000)
    # antigüedad medida desde el punto medio del trabajo de campo
    d0['w']=0.5**(((asof-d0.mid).dt.total_seconds()/86400).clip(lower=0)/HALF)
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

HOUSE_CORRECT={'CIS'}  # casas con sesgo sistemático corregido (ver house_correct)
def house_correct(P,firms=HOUSE_CORRECT,days=365):
    """Corrige el efecto casa de las reestimaciones de datos del CIS: a cada encuesta se le resta la desviación media
    de esa casa frente a la media del resto de encuestas en sus publicaciones de los 12 meses anteriores
    (sin incluirse a sí misma, para no corregir con su propio dato)."""
    P=P.copy(); keys=[k for k in PRIOR if k in P]
    for firm in firms:
        F=P[P.firm==firm].sort_values('end'); O=P[P.firm!=firm]
        dev={}
        for i,r in F.iterrows():
            a=aggregate(O,r.end)['post']; dev[i]={k:(r[k]-a[k]['mean']) for k in keys if pd.notna(r[k])}
        for i,r in F.iterrows():
            prev=[j for j in F.index if F.at[j,'end']<r.end and F.at[j,'end']>=r.end-pd.Timedelta(days=days)]
            if len(prev)<3: continue
            for k in keys:
                v=[dev[j][k] for j in prev if k in dev[j]]
                if len(v)>=3 and pd.notna(r[k]): P.at[i,k]=max(r[k]-sum(v)/len(v),0.1)
    return P

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
    P=house_correct(load_polls())
    asof=sys.argv[1] if len(sys.argv)>1 else str(P.end.max().date())
    r=aggregate(P,asof)
    print(r['date'],r['n_polls'],'encuestas'); print(pd.DataFrame(r['post']).T.to_string())
    json.dump(r,open(os.path.join(ROOT,'data','polls_post.json'),'w'),ensure_ascii=False)
