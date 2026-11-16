"""Serie semanal: media de encuestas y simulación nacional a cada domingo (sin análisis provincial ni de voto útil).

El error del día de la elección de cada semana sale de la curva histórica según los días que faltaban
para el 29-N (más de 90 días: el valor a 90). Escribe data/timeseries.json.
"""
import os, json, subprocess, sys
import pandas as pd, numpy as np
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from polls_model import load_polls, aggregate, means, house_correct, ROOT
ELECTION=pd.Timestamp('2026-11-29')
HZ=[(3,2.19),(7,2.25),(14,2.23),(21,2.31),(30,2.90),(45,2.88),(60,4.03),(90,4.80)]
def err_pts(days): return float(np.interp(min(days,90),[h for h,_ in HZ],[e for _,e in HZ]))
P=house_correct(load_polls()); b=json.load(open(os.path.join(ROOT,'data','base.json')))
last=P.end.max()
dates=list(pd.date_range('2026-01-04',last,freq='W-SUN'))
if dates[-1]!=last: dates.append(last)
weeks=[]
for d in dates:
    a=aggregate(P,d)
    if a['n_polls']<3: continue
    weeks.append(dict(date=str(d.date()),n_polls=a['n_polls'],days=int((ELECTION-d).days),err=round(err_pts((ELECTION-d).days),2),means=means(a['post'],b)))
inp=os.path.join(ROOT,'data','ts_input.json'); json.dump(dict(parties=b['parties'],provinces=b['provinces'],weeks=weeks),open(inp,'w'),ensure_ascii=False)
subprocess.run(['node',os.path.join(ROOT,'model','ts_sim.js'),inp,os.path.join(ROOT,'data','timeseries.json')],check=True)
os.remove(inp)
