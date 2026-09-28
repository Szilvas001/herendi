'use strict';
/* Herendi–Zsolnay vételkereső – dashboard. Csak a saját backend API-t hívja. */
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const ft = (n) => (n === null || n === undefined || Number.isNaN(n)) ? '–' : new Intl.NumberFormat('hu-HU', { maximumFractionDigits: 0 }).format(n) + ' Ft';
const usd = (n) => (n === null || n === undefined) ? '–' : '$' + new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(n);
const pct = (x) => (x === null || x === undefined) ? '–' : Math.round(x * 100) + '%';
const safeUrl = (s) => { try { const u = new URL(s, location.origin); return ['https:', 'http:'].includes(u.protocol) ? u.href : '#'; } catch { return '#'; } };
const TYPE = { fix: 'Fix ár', alku: 'Alkuképes', aukcio: 'Aukció', ismeretlen: 'Ismeretlen' };
const PAGE = 60;
const ASSUMPTION_FIELDS = [
  ['fx.huf_per_usd', 'HUF/USD árfolyam'],
  ['common.asking_to_sale_ratio', 'Kínálat → eladás arány'],
  ['common.inbound_shipping_huf', 'Szállítás hozzánk (Ft)'],
  ['common.profit_tax_rate', 'Adó a nyereségre'],
  ['common.risk_reserve_rate', 'Kockázati tartalék'],
  ['hu.platform_fee_rate', 'HU piactéri jutalék'],
  ['hu.packaging_huf', 'HU csomagolás (Ft)'],
  ['us.platform_fee_rate', 'eBay jutalék'],
  ['us.fx_conversion_rate', 'Devizaváltás'],
  ['us.intl_shipping_huf_small', 'USA posta, kis tárgy (Ft)'],
  ['us.intl_shipping_huf_large', 'USA posta, nagy (Ft)'],
  ['us.import_duty_rate', 'USA vám/tarifa'],
];
let defaults = {}, overrides = {}, offset = 0, lastJob = null, loading = false, modelStatus = '';

const store = {
  get(k, d) { try { const v = localStorage.getItem('hz.' + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem('hz.' + k, JSON.stringify(v)); } catch { /* privát mód */ } },
};

async function api(path, opts) {
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || data.error || ('HTTP ' + r.status));
  return data;
}

function relTime(iso) {
  if (!iso) return 'soha';
  const h = (Date.now() - new Date(iso).getTime()) / 36e5;
  if (h < 1) return Math.max(1, Math.round(h * 60)) + ' perce';
  if (h < 48) return Math.round(h) + ' órája';
  return Math.round(h / 24) + ' napja';
}

// ---------------------------------------------------------------- státusz
async function loadStatus() {
  let s;
  try { s = await api('/api/status'); } catch (e) { $('warnings').innerHTML = `<div class="bad">A szerver nem érhető el: ${esc(e.message)}</div>`; return; }
  const m = s.model;
  const pm = $('pill-model');
  if (!m) { pm.textContent = 'Modell: nincs'; pm.className = 'pill bad'; }
  else {
    pm.textContent = `Modell: ${m.version} · ${m.status.toUpperCase()}${m.loaded ? '' : ' (nincs betöltve)'}`;
    pm.className = 'pill ' + (m.status === 'validált' && m.loaded ? 'ok' : 'warn');
    pm.title = (m.reasons || []).join('\n');
  }
  const pc = $('pill-crawl');
  const ok = s.last_successful_crawl;
  const runs = Object.entries(s.crawl || {});
  if (ok) { pc.textContent = `Utolsó sikeres gyűjtés: ${relTime(ok.finished_at)} (${ok.source})`; pc.className = 'pill ok'; }
  else if (runs.length) { pc.textContent = `Adatgyűjtés: ${runs.map(([k, r]) => k + ' ' + r.status).join(', ')}`; pc.className = 'pill bad'; }
  else { pc.textContent = 'Adatgyűjtés: még nem futott (importált adat)'; pc.className = 'pill warn'; }
  pc.title = runs.map(([k, r]) => `${k}: ${r.status}, lefedettség: ${r.coverage || '–'}`).join('\n');
  const pd = $('pill-data');
  const age = s.newest_observation ? (Date.now() - new Date(s.newest_observation)) / 36e5 : null;
  const active = Object.entries(s.counts || {}).filter(([k]) => k.endsWith('/active')).reduce((a, [, v]) => a + v, 0);
  pd.textContent = `Aktív hirdetés: ${active} · legfrissebb adat ${relTime(s.newest_observation)}`;
  pd.className = 'pill ' + (age === null || age > 48 ? 'warn' : 'ok');
  $('warnings').innerHTML = (s.warnings || []).map((w) => `<div>${esc(w)}</div>`).join('');
  const fmtN = (n) => new Intl.NumberFormat('hu-HU').format(n);
  const vol = s.volume || [];
  $('volume').innerHTML = vol.map((g) => `<div class="vrow"><span>${esc(g.label)}</span>
    <div class="vbar" role="progressbar" aria-valuenow="${g.pct}" aria-valuemin="0" aria-valuemax="100"><div style="width:${Math.min(100, g.pct || 0)}%"></div></div>
    <span>${fmtN(g.have)} / ${fmtN(g.target)} (${g.pct}%)</span></div>`).join('')
    + (s.pending_image_downloads ? `<div class="vrow"><span>Letöltésre váró kép</span><span></span><span>${fmtN(s.pending_image_downloads)}</span></div>` : '');
  const hz = vol.find((g) => g.key === 'hz_records_with_images');
  if (hz) $('volume-summary').textContent = `Tanítóadat a célokhoz képest – Herendi/Zsolnay képes: ${fmtN(hz.have)} / ${fmtN(hz.target)}`;
  const running = (s.jobs || []).find((j) => j.status === 'running' || j.status === 'queued');
  showJob(running || (lastJob && s.jobs.find((j) => j.id === lastJob)));
}

function showJob(j) {
  const bar = $('jobbar');
  if (!j) { bar.hidden = true; return; }
  const labels = { harvest_ebay: 'eBay-gyűjtés', finetune_vision: 'Képenkóder finomhangolás', learning_curve: 'Tanulási görbe', crawl: 'Adatgyűjtés', import_csv: 'CSV import', import_repo: 'Import', images: 'Képfeldolgozás', train: 'Tanítás', score: 'Pontozás', pipeline: 'Teljes feldolgozás' };
  bar.hidden = false;
  const active = j.status === 'running' || j.status === 'queued';
  let msg = j.message || '';
  if (!active) { try { msg = JSON.stringify(JSON.parse(msg)).slice(0, 220); } catch { msg = msg.split('\n')[0]; } }
  $('jobtext').textContent = `${labels[j.kind] || j.kind} #${j.id}: ${j.status === 'done' ? 'kész' : j.status === 'failed' ? 'HIBA' : 'fut'} – ${msg}`;
  $('jobprogress').style.width = Math.round(100 * (j.progress || 0)) + '%';
  $('btn-cancel').hidden = !active;
  $('btn-cancel').onclick = () => api(`/api/jobs/${j.id}/cancel`, { method: 'POST' }).then(loadStatus);
  if (active) lastJob = j.id;
  else if (lastJob === j.id) { lastJob = null; refresh(); setTimeout(() => { bar.hidden = true; }, 15000); }
}

async function startJob(kind, params = {}) {
  try { const r = await api('/api/jobs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind, params }) }); lastJob = r.id; loadStatus(); }
  catch (e) { alert('Nem indítható: ' + e.message); }
}

// ---------------------------------------------------------------- szűrők
function filters() {
  const f = new FormData($('filter-form'));
  const q = new URLSearchParams();
  const market = f.get('market');
  q.set('market', market);
  if (f.get('brand')) q.set('brand', f.get('brand'));
  const price = f.get('price');
  $('custom-price').hidden = price !== 'custom';
  if (price === 'custom') { if ($('custom-price').value) q.set('max_price', $('custom-price').value); }
  else if (price) q.set('max_price', price);
  if ($('min-discount').value !== '') q.set('min_discount', $('min-discount').value);
  if ($('min-profit').value !== '') q.set('min_profit', $('min-profit').value);
  const conf = +$('min-confidence').value; $('conf-out').textContent = pct(conf);
  if (conf > 0) q.set('min_confidence', conf);
  if ($('source').value) q.set('source', $('source').value);
  const types = [...document.querySelectorAll('input[name=type]:checked')].map((x) => x.value);
  if (types.length < 3) q.set('sale_type', types.join(',') || 'none');
  if ($('only-rec').checked) q.set('only_recommended', 'true');
  if ($('only-cand').checked) q.set('only_candidates', 'true');
  if ($('hide-abstain').checked) q.set('include_abstain', 'false');
  q.set('sort', $('sort').value);
  for (const [k, v] of Object.entries(overrides)) q.set('a.' + k, v);
  return q;
}

function saveFilters() {
  const state = {};
  for (const el of $('filter-form').elements) {
    if (!el.name && !el.id) continue;
    if (el.type === 'radio' || el.type === 'checkbox') { if (el.type === 'radio' && !el.checked) continue; state[(el.name || el.id) + (el.type === 'checkbox' && el.name ? ':' + el.value : '')] = el.type === 'radio' ? el.value : el.checked; }
    else if (el.id && !el.id.startsWith('af-')) state[el.id] = el.value;
  }
  store.set('filters', state); store.set('overrides', overrides);
}

function restoreFilters() {
  const s = store.get('filters', null);
  overrides = store.get('overrides', {});
  if (!s) return;
  for (const el of $('filter-form').elements) {
    if (el.type === 'radio') { if (s[el.name] !== undefined) el.checked = s[el.name] === el.value; }
    else if (el.type === 'checkbox') { const k = el.name ? el.name + ':' + el.value : el.id; if (s[k] !== undefined) el.checked = s[k]; }
    else if (el.id && s[el.id] !== undefined && !el.id.startsWith('af-')) el.value = s[el.id];
  }
}

// ---------------------------------------------------------------- kártyák
function estBox(label, m, selected, native) {
  if (!m) return `<div class="${selected ? 'sel' : ''}">${label}<b>–</b><small>nincs becslés</small></div>`;
  const nat = native && m.currency === 'USD' ? ` · ${usd(m.value_native.q50)}` : '';
  return `<div class="${selected ? 'sel' : ''}">${label}<b>${ft(m.value_huf.q50)}</b>
    <small>${ft(m.value_huf.q10)} – ${ft(m.value_huf.q90)}${nat}</small><br><small>±10%-on belül: ${m.p_within_10 == null ? '–' : pct(m.p_within_10)}</small></div>`;
}

function card(c) {
  const m = c.market === 'HU' ? c.hu : c.us;
  const badges = [];
  if (m && m.precise) badges.push('<span class="badge good">Pontos ár (±10%)</span>');
  if (c.identity && c.identity.form_no) badges.push(`<span class="badge">${esc(c.identity.form_no)}${c.identity.pattern_code ? ' ' + esc(c.identity.pattern_code) : ''}</span>`);
  if (c.recommended) badges.push(`<span class="badge good">Ajánlott${modelStatus === 'validált' ? '' : ' – kísérleti modell'}</span>`);
  else if (c.candidate) badges.push('<span class="badge warn">Jelölt – bizonytalan</span>');
  else if (c.abstain && c.abstain.length) badges.push('<span class="badge">Nincs ajánlás</span>');
  if (c.market === 'HU' && c.other_market_flags.profitable) badges.push('<span class="badge good">USA-ba nyereséges</span>');
  if (c.market === 'US' && m && m.below_value) badges.push('<span class="badge good">USA-érték alatt</span>');
  const img = c.image ? `<img loading="lazy" src="${esc(safeUrl(c.image))}" alt="" onerror="this.replaceWith(document.createTextNode('kép nem tölthető'))">` : 'nincs kép';
  const profitCls = (v) => v === null || v === undefined ? '' : v >= 0 ? 'pos' : 'neg';
  const auction = c.sale_type === 'aukcio';
  const profitLabel = auction ? 'Ha ezen a licitten nyered' : 'Becsült nettó nyereség';
  return `<article class="card ${c.recommended ? 'rec' : c.candidate ? 'cand' : ''}">
    <div class="thumb">${img}<div class="badges">${badges.join('')}</div></div>
    <div class="cbody">
      <h3 class="ctitle" title="${esc(c.title)}">${esc(c.title)}</h3>
      <div class="price"><strong>${ft(c.price_huf)}</strong><span class="type">${TYPE[c.sale_type] || c.sale_type}${auction ? ` · ${c.bid_count ?? '?'} licit${c.end_time ? ' · vége ' + new Date(c.end_time).toLocaleString('hu-HU', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''}` : ''}</span></div>
      <div class="est">${estBox('Magyar érték', c.hu, c.market === 'HU')}${estBox('Amerikai érték', c.us, c.market === 'US', true)}</div>
      ${m ? `<div class="profit"><span>${profitLabel}</span><span class="${profitCls(m.profit_huf)}">${ft(m.profit_huf)} (${m.roi_pct ?? '–'}%)</span></div>
      <div class="profit"><span>Konzervatív (alsó becslés)</span><span class="${profitCls(m.conservative_profit_huf)}">${ft(m.conservative_profit_huf)} (${m.conservative_roi_pct ?? '–'}%)</span></div>
      ${auction ? `<div class="profit"><span>Max. javasolt licit</span><span>${ft(m.max_bid_huf)}</span></div>` : ''}` : ''}
      <p class="reason">${esc(c.reason || '')}</p>
      <div class="risks">${(c.risks || []).slice(0, 3).map((r) => `<span>${esc(r)}</span>`).join('')}</div>
      <div class="cfoot"><span title="${esc(c.last_checked)} · modell ${esc(c.model_version)}">${esc(c.source)} · ellenőrizve ${relTime(c.last_checked)}</span>
        <span class="btns"><button class="secondary" data-detail="${c.id}">Részletek</button>
        <a class="btn" href="${esc(safeUrl(c.url))}" target="_blank" rel="noopener noreferrer">Hirdetés megnyitása</a></span></div>
    </div></article>`;
}

async function refresh(append = false) {
  if (loading) return;
  loading = true;
  if (!append) offset = 0;
  saveFilters();
  const q = filters(); q.set('limit', PAGE); q.set('offset', offset);
  try {
    const r = await api('/api/deals?' + q.toString());
    if (r.error) { $('cards').innerHTML = `<div class="empty">${esc(r.error)}</div>`; $('summary').textContent = ''; return; }
    modelStatus = r.model_status || '';
    const html = r.items.map(card).join('');
    $('cards').innerHTML = append ? $('cards').innerHTML + html : (html || '<div class="empty">Nincs a szűrőknek megfelelő hirdetés. Lazíts a feltételeken, vagy kapcsold ki a „Csak ajánlott vagy jelölt” szűrőt – a rendszer bizonytalan becslésnél szándékosan tartózkodik az ajánlástól.</div>');
    offset += r.items.length;
    $('btn-more').hidden = offset >= r.total;
    const mk = q.get('market') === 'HU' ? 'magyar' : 'amerikai';
    $('summary').textContent = `${r.total} találat (${mk} célpiac) · ${r.summary.recommended} ajánlott · ${r.summary.candidate} bizonytalan jelölt · ${r.summary.below_value} piaci érték alatt · ${r.summary.profitable} konzervatívan nyereséges`;
  } catch (e) { $('cards').innerHTML = `<div class="empty">Hiba: ${esc(e.message)}</div>`; }
  finally { loading = false; }
}

// ---------------------------------------------------------------- részletek
function costTable(sc) {
  if (!sc) return '<p>Nincs ár, a nyereség nem számítható.</p>';
  const rows = Object.entries(sc.cost_items).map(([k, v]) => `<tr><td>${esc(k)}</td><td class="num">${ft(v)}</td></tr>`).join('');
  return `<table><tr><td>Várható bevétel</td><td class="num">${ft(sc.revenue_huf)}</td></tr>
    <tr><td>Vételár</td><td class="num">−${ft(sc.purchase_huf)}</td></tr>${rows}
    <tr><td>Adó</td><td class="num">−${ft(sc.tax_huf)}</td></tr>
    <tr><th>Nettó nyereség (megtérülés)</th><th class="num">${ft(sc.profit_huf)} (${sc.roi_pct ?? '–'}%)</th></tr></table>`;
}

function marketBlock(name, m) {
  if (!m) return `<h3>${name}</h3><p>Nincs becslés ehhez a piachoz.</p>`;
  const nat = m.currency === 'USD' ? ` (${usd(m.value_native.q10)} – ${usd(m.value_native.q50)} – ${usd(m.value_native.q90)})` : '';
  const comps = (m.comparables || []).map((c) => `<tr><td>${c.url ? `<a href="${esc(safeUrl(c.url))}" target="_blank" rel="noopener noreferrer">${esc(c.title)}</a>` : esc(c.title)}</td>
    <td class="num">${c.currency === 'USD' ? usd(c.price) : ft(c.price)}</td><td>${esc(c.price_type)}</td><td>${esc(c.observed_at)}</td><td class="num">${c.similarity}</td></tr>`).join('');
  return `<h3>${name}</h3>
    <p><b>${ft(m.value_huf.q50)}</b> (80%-os intervallum: ${ft(m.value_huf.q10)} – ${ft(m.value_huf.q90)})${nat}<br>
    ±10%-on belüli valószínűség: ${m.p_within_10 == null ? '–' : pct(m.p_within_10)}${m.precise ? ' · <b>pontos ár (validált)</b>' : ''}
    · azonos termék eladásai: ${m.sku && m.sku.n_exact != null ? m.sku.n_exact : 0}, azonos formaszám: ${m.sku && m.sku.n_form != null ? m.sku.n_form : 0}<br>
    Megbízhatóság (±25%): ${pct(m.confidence)} · modell: ${esc(m.model)} · célváltozó: ${m.basis === 'asking' ? 'kínálati ár (kísérleti)' : 'realizált ár'}
    ${m.revenue_factor !== 1 ? ` · várható eladás = érték × ${m.revenue_factor}` : ''}</p>
    <p>${esc(m.reason)}</p>
    ${m.abstain_reasons.length ? `<p class="neg">Tartózkodás: ${esc(m.abstain_reasons.join('; '))}</p>` : ''}
    <div class="dgrid"><div><h3>Alap forgatókönyv (medián)</h3>${costTable(m.base)}</div><div><h3>Konzervatív (alsó becslés)</h3>${costTable(m.conservative)}</div></div>
    <h3>Összehasonlítható tételek</h3>
    <table><tr><th>Tétel</th><th class="num">Ár</th><th>Ártípus</th><th>Dátum</th><th class="num">Hasonlóság</th></tr>${comps || '<tr><td colspan="5">nincs</td></tr>'}</table>
    <h3>Kockázatok</h3><ul>${m.risks.map((r) => `<li>${esc(r)}</li>`).join('')}</ul>`;
}

async function openDetail(id) {
  const q = new URLSearchParams(); for (const [k, v] of Object.entries(overrides)) q.set('a.' + k, v);
  let d;
  try { d = await api(`/api/listings/${id}?` + q.toString()); } catch (e) { alert(e.message); return; }
  const l = d.listing, a = d.assessment;
  $('d-title').textContent = l.title;
  const imgs = d.images.length ? d.images.map((i) => `<a href="${esc(safeUrl(i.remote || i.src))}" target="_blank" rel="noopener noreferrer"><img src="${esc(safeUrl(i.src))}" alt="" loading="lazy"></a>`).join('') : '<p>Nincs letöltött kép.</p>';
  const hist = d.history.map((h) => `<tr><td>${esc(h.observed_at.slice(0, 16).replace('T', ' '))}</td><td class="num">${ft(h.price_huf)}</td><td>${esc(h.status || '')}</td><td>${esc(h.via)}</td></tr>`).join('');
  const f = (d.estimate || {}).features || {};
  const as = d.assumptions;
  $('d-body').innerHTML = `<div class="gallery">${imgs}</div>
    <p><b>${ft(l.price_huf)}</b> · ${TYPE[l.sale_type] || l.sale_type}${l.sale_type === 'aukcio' ? ` · ${l.bid_count ?? '?'} licit · vége: ${esc(l.end_time || '?')} · <b>a licit nem végleges ár</b>` : ''}
    · státusz: ${esc(l.status)} (${esc(l.status_reason || '')})<br>
    <a class="btn" href="${esc(safeUrl(l.url))}" target="_blank" rel="noopener noreferrer">Hirdetés megnyitása</a></p>
    <h3>Pontos termékazonosítás</h3>
    <p>${a && a.identity ? `Cikkszám-kulcs: <b>${esc(a.identity.sku_key)}</b> · formaszám ${esc(a.identity.form_no)} · minta ${esc(a.identity.pattern_code || '–')} · alap: ${esc(a.identity.basis || '')}` : 'Nincs azonosítva (formaszám/minta ismeretlen) – pontos piaci ár ehhez nem adható.'}</p>
    <h3>Azonosított jellemzők</h3>
    <p>Gyártó: ${esc(f.brand || '–')} · típus: ${esc(f.object_type || '–')} · dekor: ${esc(f.decor || '–')} · méret: ${f.size_cm ? f.size_cm + ' cm' : '–'} · darab: ${f.pieces || '–'} · állapot: ${esc(f.condition || '–')} · jelzések: ${esc(f.mark_flags || '–')}</p>
    ${a ? `<p>Hiányzó információ: ${esc(a.missing_info.join('; ') || 'nincs')}</p>` : ''}
    <h3>Leírás</h3><div class="desc">${esc(l.description || 'A részletes oldal még nem volt letöltve.')}</div>
    ${a ? marketBlock('Magyar piac', a.markets.HU) + marketBlock('Amerikai piac', a.markets.US) : '<p>Nincs becslés (nincs modell vagy nem azonosított tétel).</p>'}
    <h3>Árkövetés</h3><table><tr><th>Időpont (UTC)</th><th class="num">Ár</th><th>Státusz</th><th>Forrás</th></tr>${hist}</table>
    <h3>Számítási feltételezések</h3>
    <p class="kv">Árfolyam: ${as.fx.huf_per_usd} Ft/USD (${esc(as.fx.as_of)}); ${esc(as.fx.note)}<br>
    Közös: ${esc(JSON.stringify(as.common))}<br>HU: ${esc(JSON.stringify(as.hu))}<br>US: ${esc(JSON.stringify(as.us))}</p>
    <h3>Visszakövethetőség</h3>
    <p class="kv">Hirdetés #${l.id} · ${esc(l.source)}:${esc(l.source_id)} · eredet: ${esc(l.origin)} · első észlelés ${esc(l.first_seen)} · utolsó észlelés ${esc(l.last_seen)} · utolsó ellenőrzés ${esc(l.last_checked || '–')}<br>
    Modellverzió: ${esc(d.estimate?.model_version || '–')} (${esc(d.model?.status || '')}) · bemenet-hash: ${esc(d.estimate?.input_hash || '–')} · becsülve: ${esc(d.estimate?.estimated_at || '–')}</p>`;
  $('detail').showModal();
}

// ---------------------------------------------------------------- feltételezések
async function loadAssumptions() {
  try { defaults = await api('/api/assumptions'); } catch { return; }
  $('assumption-fields').innerHTML = ASSUMPTION_FIELDS.map(([k, label]) => {
    const [sec, key] = k.split('.');
    const v = overrides[k] ?? defaults[sec]?.[key];
    return `<label class="af">${esc(label)}<input id="af-${k}" data-key="${k}" type="number" step="any" min="0" value="${esc(v)}"></label>`;
  }).join('');
  document.querySelectorAll('#assumption-fields input').forEach((el) => el.addEventListener('change', () => {
    const [sec, key] = el.dataset.key.split('.');
    if (el.value === '' || +el.value === defaults[sec][key]) delete overrides[el.dataset.key]; else overrides[el.dataset.key] = +el.value;
    refresh();
  }));
}

// ---------------------------------------------------------------- események
let timer;
$('filter-form').addEventListener('input', (e) => { if (e.target.closest('#assumption-fields')) return; clearTimeout(timer); timer = setTimeout(() => refresh(), 250); });
$('btn-more').addEventListener('click', () => refresh(true));
$('cards').addEventListener('click', (e) => { const b = e.target.closest('[data-detail]'); if (b) openDetail(b.dataset.detail); });
$('d-close').addEventListener('click', () => $('detail').close());
$('detail').addEventListener('click', (e) => { if (e.target === $('detail')) $('detail').close(); });
$('btn-filters').addEventListener('click', () => $('filters').classList.toggle('open'));
$('btn-crawl').addEventListener('click', () => startJob('crawl', { source: 'vatera' }));
$('btn-score').addEventListener('click', () => startJob('score', {}));
$('btn-harvest').addEventListener('click', () => startJob('harvest_ebay', { images: true }));
$('btn-train').addEventListener('click', () => { if (confirm('Új modellverzió tanítása a jelenlegi adatokon? (néhány perc)')) startJob('train', {}); });
$('btn-reset-assumptions').addEventListener('click', () => { overrides = {}; loadAssumptions(); refresh(); });
$('file-import').addEventListener('change', async (e) => {
  const file = e.target.files[0]; if (!file) return;
  const fd = new FormData(); fd.append('file', file);
  try { const r = await api('/api/import?type=listings', { method: 'POST', body: fd }); lastJob = r.id; loadStatus(); }
  catch (err) { alert('Import hiba: ' + err.message); }
  e.target.value = '';
});

restoreFilters();
loadAssumptions();
loadStatus();
refresh();
setInterval(loadStatus, 4000);
