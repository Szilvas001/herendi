/* No remote scripts, analytics, credentials or API calls. data.js is generated. */
'use strict';
const $=id=>document.getElementById(id), fmt=n=>new Intl.NumberFormat('hu-HU',{maximumFractionDigits:0}).format(n)+' Ft';
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeUrl=s=>{try{const u=new URL(s);return u.protocol==='https:'?u.href:'#'}catch{return '#'}};
let calculated=[];
function render(){
 if(!window.REPORT){$('error').textContent='Az adatfájl hiányzik. Futtasd: python -m elemzes.export_dashboard';return;}
 const fx=+$('fx').value,fee=+$('fee').value/100,risk=+$('risk').value/100,extra=+$('extra').value;
 if(![fx,fee,risk,extra].every(Number.isFinite)||fx<=0||fee<0||risk<0||fee+risk>=1||extra<0){$('error').textContent='Adj meg érvényes költségeket; a díj és tartalék összege 100% alatt legyen.';calculated=[];return;}
 $('error').textContent='';const mode=$('scenario').value;
 calculated=REPORT.items.map(r=>{const overhead=Object.values(r.costs_huf).reduce((a,b)=>a+b,0)+($('market').value==='us'?extra:0),sale=r.sale_eur[mode]*fx,capital=r.purchase_huf+overhead,profit=sale*(1-fee-risk)-capital;return {...r,sale,capital,profit,roi:100*profit/capital,ceiling:Math.max(0,Math.floor(sale*(1-fee-risk)/1.3-overhead))};});
 $('notice').textContent=REPORT.warning;
 $('metrics').innerHTML=`<div class="metric">Kutatási jelöltek<strong>${calculated.length}</strong></div><div class="metric">Igazolt likvid vételek<strong>0</strong></div><div class="metric">Vizsgált keresőkártyák<strong>${REPORT.coverage.candidates}</strong></div><div class="metric">Forgatókönyv tőkeigénye<strong>${fmt(calculated.reduce((s,r)=>s+r.capital,0))}</strong></div>`;
 $('cards').innerHTML=calculated.map((r,i)=>`<article><span class="tag">0${i+1} / ${esc(r.brand)} · KUTATÁSI JELÖLT</span><h2>${esc(r.name)}</h2><p>${esc(r.thesis)}</p><dl><dt>Kiinduló ár</dt><dd>${fmt(r.purchase_huf)}</dd><dt>Eladási feltételezés</dt><dd>${fmt(r.sale)}</dd><dt>Adózás előtti ROI</dt><dd class="${r.roi<0?'negative':'positive'}">${r.roi.toFixed(1)}%</dd><dt>Tervezési eladási idő</dt><dd>${esc(mode==='high'?r.days_high:r.days)} nap</dd></dl><p><b>Időbecslés: alacsony bizonyosság.</b> Nem mért eladási sebesség; sikertelen értékesítés is lehetséges.</p><p class="detail">${esc(r.condition)}</p><p>${esc(r.price_basis)}</p><p><a href="${esc(safeUrl(r.url))}" target="_blank" rel="noopener noreferrer">Hazai hirdetés ↗</a></p><details><summary>Források és ellenőrzés</summary><p>${esc(r.checked_at)}</p>${r.sources.map(s=>`<p><a href="${esc(safeUrl(s.url))}" target="_blank" rel="noopener noreferrer">${esc(s.label)}</a> — ${esc(s.kind)}</p>`).join('')}</details></article>`).join('');
 $('rows').innerHTML=calculated.map(r=>`<tr><td>${esc(r.name)}</td><td>${fmt(r.purchase_huf)}</td><td>${fmt(r.capital)}</td><td>${fmt(r.profit)}</td><td>${r.roi.toFixed(1)}%</td><td>${fmt(r.ceiling)}</td></tr>`).join('');
 $('foot').textContent=`Adatellenőrzés: ${REPORT.checked_at}. ${REPORT.method} Az USA extra tervezési tartalék, nem vám- vagy postai árajánlat. Adó, munkaidő és tőkeköltség nincs levonva. SaaS prototípus: helyben futó, bejelentkezés nélküli kutatási felület.`;
}
document.querySelectorAll('input,select').forEach(el=>el.addEventListener('input',render));
$('download').addEventListener('click',()=>{render();if(!calculated.length)return;const u=URL.createObjectURL(new Blob([JSON.stringify({scenario:$('scenario').value,market:$('market').value,items:calculated},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download='hungarian-finds-scenario.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);});render();
