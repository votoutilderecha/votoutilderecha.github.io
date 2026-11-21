// Simula cada semana de la serie con el mismo motor de la página (model/template.html).
const fs=require('fs'),path=require('path');
const tpl=fs.readFileSync(path.join(__dirname,'template.html'),'utf8');
const code=tpl.split('/*ENGINE-START*/')[1].split('/*ENGINE-END*/')[0];const m={exports:{}};new Function('module',code)(m);const E=m.exports;
const I=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));const M=E.setup(I);const P=I.parties;const NP=P.length;const N=3000;
const q=(a,p)=>{const s=Array.from(a).sort((x,y)=>x-y);return s[Math.min(s.length-1,Math.floor(p*(s.length-1)))]};
const iPP=P.indexOf('PP'),iPS=P.indexOf('PSOE');
const out=I.weeks.map(w=>{let mu=P.map(p=>p==='Otros'?0:w.means[p].mean);mu[P.indexOf('Otros')]=Math.max(100-mu.reduce((a,b)=>a+b,0),0.5);const t=mu.reduce((a,b)=>a+b,0);mu=mu.map(x=>x/t);
  const sd=P.map(p=>p==='Otros'?0.003:w.means[p].sd/100);
  const Mw=w.provinces?E.setup({parties:P,provinces:w.provinces}):M;
  const R=E.simulate(Mw,{N,mu,sd,unc:w.err/2.2,delta:0.01,seed:17});
  const parties={};P.forEach((p,j)=>{if(p==='Otros')return;parties[p]={vote:+(mu[j]*100).toFixed(2),med:q(R.natSeats[j],.5),lo:q(R.natSeats[j],.05),hi:q(R.natSeats[j],.95)}});
  const bs={R:new Int32Array(N),L:new Int32Array(N),O:new Int32Array(N)};for(let j=0;j<NP;j++){const k=R.RIGHT[j]?'R':R.LEFT[j]?'L':'O';for(let n=0;n<N;n++)bs[k][n]+=R.natSeats[j][n]}
  const blocs={};for(const k of ['R','L','O']){const v=k==='R'?R.voteR:k==='L'?R.voteL:R.voteO;let maj=0;for(let n=0;n<N;n++)if(bs[k][n]>=176)maj++;
    blocs[k]={vote:+(q(v,.5)*100).toFixed(2),med:q(bs[k],.5),lo:q(bs[k],.05),hi:q(bs[k],.95),pmaj:+(maj/N).toFixed(3)}}
  let pv=0,pp=0;for(let n=0;n<N;n++){if(R.blocPV[n]>=176)pv++;if(R.natSeats[iPP][n]>R.natSeats[iPS][n])pp++}
  return{date:w.date,n_polls:w.n_polls,days:w.days,err:w.err,p_ppvox:+(pv/N).toFixed(3),p_pp_gt_psoe:+(pp/N).toFixed(3),ppvox:{med:q(R.blocPV,.5),lo:q(R.blocPV,.05),hi:q(R.blocPV,.95)},parties,blocs}});
fs.writeFileSync(process.argv[3],JSON.stringify({sims_per_week:N,weeks:out}));
console.log(out.length,'semanas');out.slice(-6).forEach(w=>console.log(w.date,w.n_polls,'err',w.err,'P176',w.p_ppvox,'PP+Vox',w.ppvox.med,'PP',w.parties.PP.vote,w.parties.PP.med,'Vox',w.parties.Vox.vote,w.parties.Vox.med,'PSOE',w.parties.PSOE.vote,w.parties.PSOE.med));
