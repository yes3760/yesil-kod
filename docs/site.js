'use strict';
// Yeşil Kod sitesi: tanıtım + Dashboard (kod testi) + Analizler (bu cihazdaki geçmiş) + Kurallar.
// Analiz ve ölçüm motor.js'teki Web Worker'da, standdaki Python motorunun aynısıyla çalışır.
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const VIEWS = ['proje', 'dene', 'analizler', 'kurallar'];
const BASE_TITLE = document.title;
const KEY = 'yk-analizler-v1', MAX_KAYIT = 300, LINE_H = 22, PAD = 12;
const IS_MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
let LANG = 'tr', SAMPLES = [], RULES = [], HIST = [];
let worker = null, seq = 0, engine = 'idle';
const pending = new Map();
const cur = {sample: 0, result: null, code: null, stale: false, tab: 'bulgular', measuring: false, autoRun: false};

const T = {
  tr: {
    engine: {idle: 'Motor ilk kullanımda yüklenir (~10 MB)', loading: 'Motor yükleniyor…', ready: 'Motor hazır · bu cihazda çalışıyor', error: 'Motor yüklenemedi; bağlantını kontrol et'},
    analyse: 'Analiz et', analysing: 'İnceleniyor…', loadingBtn: 'Motor yükleniyor…', lines: n => `${nf(n)} satır`, privacy: 'Kod bu cihazdan çıkmaz',
    scoreTip: 'Skor bulgulardan hesaplanır: yüksek önemli −25, orta −10, bilgi −3. Enerji ölçümü değildir.',
    startEmpty: '<b>Henüz analiz yok.</b> Bir örnek seç ya da kodunu yapıştır, sonra <b>Analiz et</b>’e bas.',
    stale: 'Kod değişti; aşağıdaki sonuçlar önceki sürüme ait. Yeniden analiz et.',
    none: 'Bilinen bir enerji israfı kalıbı bulunamadı.', line: 'satır', autoTag: 'otomatik düzeltilir', adviceTag: 'öneri',
    noFix: 'Otomatik düzeltilecek kalıp yok. Bulgular sekmesindeki önerilere bakın.',
    copy: 'Düzeltilmiş kodu kopyala', copied: 'Kopyalandı', download: 'İndir (.py)', apply: 'Editöre al',
    kept: 'Yorumlar ve biçim korundu; yalnızca değişen satırlar yeniden yazıldı.', reformatted: 'Bu kodda biçim korunamadı; motor kodu baştan yazdı.',
    measureIntro: 'İki sürüm bu cihazda çalıştırılır, çıktıları karşılaştırılır ve harcadıkları işlemci süresi ölçülür.',
    measure: 'Bu cihazda ölç', measuring: 'Ölçülüyor… birkaç saniye sürebilir.', again: 'Tekrar ölç',
    notScenario: 'Ölçüm, verisiyle birlikte gelen hazır senaryolarda yapılır; kendi kodun çalıştırılmaz. Bir senaryo seç:',
    less: 'daha az işlemci süresi, birebir aynı sonuç', orig: 'Özgün kod', fixed: 'Motorun yazdığı', perReq: 'istek başına',
    same: n => `${nf(n)} kayıtlık çıktı iki sürümde aynı`, queries: (a, b) => `Veritabanı sorgusu ${nf(a)} → ${nf(b)}`,
    notSame: 'İki sürümün çıktısı farklı çıktı; düzeltme reddedildi.', fail: 'Motor yüklenemedi. Bağlantını kontrol edip tekrar dene.',
    fine: 'Tarayıcı cihazın güç tüketimini okuyamaz; aynı işlemcide enerji işlemci süresiyle orantılı olduğu için oran süreden hesaplanır. Standdaki panel enerjiyi donanımdan ölçüp karbona çevirir.',
    histEmpty: '<b>Henüz analiz yok.</b> Dashboard’da bir kod analiz et; sonuçlar burada birikir.', goDash: 'Dashboard’a git',
    noData: 'Henüz veri yok.', noMeas: 'Henüz ölçüm yok. Dashboard’da bir senaryo seçip Ölçüm sekmesinden ölç.',
    allRules: 'Bütün kurallar', search: 'Kodda ya da adda ara', cols: ['TARİH', 'KOD', 'BULGULAR', 'DÜZELTME', 'ÖLÇÜM', ''],
    open: 'Aç', del: 'Sil', confirmAll: 'Bu cihazdaki bütün analizler silinsin mi?', noMatch: 'Filtreyle eşleşen analiz yok.',
    times: (n, k) => `${nf(n)} kez, ${nf(k)} analizde`, tryIt: 'Dashboard’da dene', autoFix: 'Motor düzeltir', advice: 'Öneri verir',
    sev: {'yüksek': 'yüksek', 'orta': 'orta', 'bilgi': 'bilgi'}, fileErr: 'Dosya okunamadı.',
  },
  en: {
    engine: {idle: 'The engine loads on first use (~10 MB)', loading: 'Loading engine…', ready: 'Engine ready · running on this device', error: 'Could not load the engine; check your connection'},
    analyse: 'Analyse', analysing: 'Analysing…', loadingBtn: 'Loading engine…', lines: n => `${nf(n)} lines`, privacy: 'Code never leaves this device',
    scoreTip: 'The score is computed from findings: high −25, medium −10, info −3. It is not an energy measurement.',
    startEmpty: '<b>No analysis yet.</b> Pick an example or paste your code, then press <b>Analyse</b>.',
    stale: 'The code changed; the results below belong to the previous version. Analyse again.',
    none: 'No known energy-waste pattern found.', line: 'line', autoTag: 'fixed automatically', adviceTag: 'advice',
    noFix: 'No pattern to fix automatically. See the advice in the Findings tab.',
    copy: 'Copy fixed code', copied: 'Copied', download: 'Download (.py)', apply: 'Load into editor',
    kept: 'Comments and formatting kept; only the changed lines were rewritten.', reformatted: 'Formatting could not be kept for this code; the engine rewrote it.',
    measureIntro: 'Both versions run on this device; their outputs are compared and their CPU time is measured.',
    measure: 'Measure on this device', measuring: 'Measuring… this can take a few seconds.', again: 'Measure again',
    notScenario: 'Measurement runs on the ready-made scenarios that come with their data; your own code is never executed. Pick a scenario:',
    less: 'less CPU time, identical output', orig: 'Original code', fixed: 'Engine’s version', perReq: 'per request',
    same: n => `${nf(n)}-row output identical in both versions`, queries: (a, b) => `Database queries ${nf(a)} → ${nf(b)}`,
    notSame: 'The outputs differ; the fix was rejected.', fail: 'Could not load the engine. Check your connection and try again.',
    fine: 'Browsers cannot read the device’s power draw; on the same processor energy is proportional to CPU time, so the ratio is computed from time. The stand panel measures energy from hardware and converts it to carbon.',
    histEmpty: '<b>No analyses yet.</b> Analyse some code in the Dashboard; results collect here.', goDash: 'Go to Dashboard',
    noData: 'No data yet.', noMeas: 'No measurements yet. Pick a scenario in the Dashboard and measure it in the Measure tab.',
    allRules: 'All rules', search: 'Search code or name', cols: ['DATE', 'CODE', 'FINDINGS', 'FIXES', 'MEASURED', ''],
    open: 'Open', del: 'Delete', confirmAll: 'Delete every analysis on this device?', noMatch: 'No analysis matches the filter.',
    times: (n, k) => `${nf(n)} times, in ${nf(k)} analyses`, tryIt: 'Try in Dashboard', autoFix: 'Engine fixes it', advice: 'Gives advice',
    sev: {'yüksek': 'high', 'orta': 'medium', 'bilgi': 'info'}, fileErr: 'Could not read the file.',
  },
};
let CATS = {};                     // kurallar.json: kategori adları (tr/en)
const FIX_EN = {YK001: 'Single-row query in the loop replaced by one batched IN query.', YK002: 'List converted to a set before the loop.',
                YK003: 'Invariant call moved out of the loop; it now runs once.', YK004: 'Cache added; each sub-result is computed once.',
                YK011: 'min()/max() used instead of sorting and taking the first element; one pass.',
                YK029: 'range(...) iterated directly instead of list(range(...)); no copy is made.',
                YK062: 'Needless double conversion removed; the data is not copied again.',
                YK064: 'A comprehension that only copied was replaced by a direct list()/set()/dict() call.',
                YK065: 'A generator is used instead of a list; elements do not pile up in memory.',
                YK066: 'Needless call around a literal removed.',
                YK113: 'Generator rewritten as a direct list, set or dict comprehension.'};
const t = () => T[LANG];
const nf = (v, d = 0) => Number(v).toLocaleString(LANG === 'en' ? 'en-GB' : 'tr-TR', {maximumFractionDigits: d, minimumFractionDigits: d});
const fmtS = s => s >= 1 ? nf(s, 2) + ' s' : s >= 1e-3 ? nf(s * 1e3, 1) + ' ms' : nf(s * 1e6, 0) + ' µs';
const big = v => (v >= 100 ? nf(v, 0) : v >= 10 ? nf(v, 1) : nf(v, 2)) + '×';
const ruleOf = k => RULES.find(r => r.kural === k);
const ruleTitle = (k, fallback) => { const r = ruleOf(k); return r ? (LANG === 'en' ? r.baslik_en : r.baslik) : fallback || k; };
const ruleAdvice = (k, fallback) => { const r = ruleOf(k); return r ? (LANG === 'en' ? r.oneri_en : r.oneri) : fallback || ''; };
const isAuto = k => (RULES.find(r => r.kural === k) || {}).otomatik;

// ------------------------------------------------------------------ motor (Web Worker)
function setEngine(s) {
  engine = s;
  $('#engine').className = 'engine ' + s;
  $('#engineTxt').textContent = t().engine[s];
  if (!cur.busy) $('#anTxt').textContent = t().analyse;
}
function motor(msg) {
  if (!worker) {
    worker = new Worker('motor.js');
    worker.onmessage = e => {
      const p = pending.get(e.data.id); pending.delete(e.data.id);
      if (p) e.data.ok ? p.ok(e.data.sonuc) : p.bad(new Error(e.data.hata));
    };
    worker.onerror = e => { for (const p of pending.values()) p.bad(new Error(e.message)); pending.clear(); worker.terminate(); worker = null; setEngine('error'); };
  }
  if (engine !== 'ready') setEngine('loading');
  return new Promise((ok, bad) => { const id = ++seq; pending.set(id, {ok, bad}); worker.postMessage({id, ...msg}); })
    .then(r => { setEngine('ready'); return r; }, e => { setEngine('error'); throw e; });
}
function warmUp() {
  if (engine === 'idle' || engine === 'error') motor({tip: 'hazirla'}).then(() => {
    if (cur.autoRun && !cur.result && $('#code').value === (SAMPLES[cur.sample] || {}).kod) analyse();
  }, () => {});
}

// ------------------------------------------------------------------ geçmiş (yalnızca bu tarayıcı)
function loadHist() {
  try { HIST = JSON.parse(localStorage.getItem(KEY) || '[]'); if (!Array.isArray(HIST)) HIST = []; } catch (e) { HIST = []; }
}
function saveHist() {
  HIST = HIST.slice(0, MAX_KAYIT);
  for (;;) {
    try { localStorage.setItem(KEY, JSON.stringify(HIST)); break; }
    catch (e) { if (HIST.length <= 1) break; HIST.pop(); }   // kota dolduysa en eskiyi at
  }
  updateNavCount();
}
function updateNavCount() {
  const c = $('#navCount'); c.hidden = !HIST.length; c.textContent = HIST.length;
}
function codeTitle(kod) {
  const defs = [...kod.matchAll(/^\s*(?:async\s+)?def\s+(\w+)/gm)].map(m => m[1]);
  if (defs.length) return defs[0] + '()' + (defs.length > 1 ? ` +${defs.length - 1}` : '');
  const first = kod.split('\n').map(s => s.trim()).find(Boolean) || '—';
  return first.length > 40 ? first.slice(0, 40) + '…' : first;
}
function recordAnalysis(kod, r) {
  const i = HIST.findIndex(h => h.kod === kod);
  const old = i >= 0 ? HIST.splice(i, 1)[0] : null;
  const s = SAMPLES.findIndex(x => x.kod === kod);
  HIST.unshift({
    id: old ? old.id : Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
    t: new Date().toISOString(), ad: codeTitle(kod), ornek: s >= 0 ? s : null, kod,
    satir: kod.split('\n').length, hata: r.hata || null,
    bulgular: (r.bulgular || []).map(b => ({kural: b.kural, onem: b.onem, satir: b.satir})),
    duzeltme: (r.duzeltmeler || []).length, bicim: !!r.bicim_korundu, olcum: old ? old.olcum : null,
  });
  saveHist();
}
function recordMeasure(kod, m) {
  const h = HIST.find(x => x.kod === kod);
  if (h) { h.olcum = {kat: m.kat, ozgun_s: m.ozgun_s, duzeltilmis_s: m.duzeltilmis_s, cikti: m.cikti, sorgu: m.sorgu, t: new Date().toISOString()}; saveHist(); }
}
const histLabel = h => h.ornek != null && SAMPLES[h.ornek] && SAMPLES[h.ornek].kod === h.kod ? (LANG === 'en' ? SAMPLES[h.ornek].en : SAMPLES[h.ornek].tr) : h.ad;

// ------------------------------------------------------------------ editör
const ta = () => $('#code');
function sampleId() {
  const s = SAMPLES.find(x => x.kod === ta().value);
  return s && s.id ? s.id : null;
}
function paintEditor() {
  const n = ta().value.split('\n').length;
  const flagged = {};
  if (cur.result && !cur.stale) for (const b of cur.result.bulgular || []) {
    const rank = {'yüksek': 0, 'orta': 1, 'bilgi': 2};
    if (!(b.satir in flagged) || rank[b.onem] < rank[flagged[b.satir]]) flagged[b.satir] = b.onem;
  }
  let g = '';
  for (let i = 1; i <= n; i++) g += `<div${i in flagged ? ' class="f"' : ''}>${i}</div>`;
  $('#gut').innerHTML = g + '<div></div><div></div>';
  $('#hl').innerHTML = Object.entries(flagged).map(([l, s]) => `<div class="${s}" style="top:${PAD + (l - 1) * LINE_H}px"></div>`).join('') +
    (cur.sel ? `<div class="sel" style="top:${PAD + (cur.sel - 1) * LINE_H}px"></div>` : '');
  $('#lines').textContent = t().lines(n);
  syncScroll();
}
function syncScroll() {
  $('#gut').scrollTop = ta().scrollTop;
  $('#hl').style.transform = `translateY(${-ta().scrollTop}px)`;
}
function gotoLine(n) {
  const L = ta().value.split('\n');
  let s = 0;
  for (let i = 0; i < n - 1; i++) s += L[i].length + 1;
  ta().focus();
  ta().setSelectionRange(s, s + (L[n - 1] || '').length);
  ta().scrollTop = Math.max(0, (n - 1) * LINE_H - ta().clientHeight / 3);
  cur.sel = n; paintEditor();
  setTimeout(() => { cur.sel = null; paintEditor(); }, 1600);
}
function setCode(kod, sampleIdx = null) {
  ta().value = kod;
  cur.sample = sampleIdx; cur.result = null; cur.stale = false; cur.sel = null;
  ta().scrollTop = 0;
  renderChips(); paintEditor(); renderResult();
}
function onInput() {
  if (cur.result && !cur.stale) { cur.stale = true; renderResult(); }
  const i = SAMPLES.findIndex(x => x.kod === ta().value);
  if ((i >= 0 ? i : null) !== cur.sample) { cur.sample = i >= 0 ? i : null; renderChips(); }
  paintEditor();
  if (cur.tab === 'olcum') renderMeasureTab();
}
function onKey(e) {
  if (e.key === 'Tab' && !e.shiftKey) {
    e.preventDefault();
    const s = ta().selectionStart;
    ta().setRangeText('    ', s, ta().selectionEnd, 'end');
    onInput();
  } else if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); analyse(); }
}
function renderChips() {
  $('#chips').innerHTML = SAMPLES.map((s, i) =>
    `<button class="chip" data-i="${i}" aria-pressed="${i === cur.sample}">${esc(LANG === 'en' ? s.en : s.tr)}</button>`).join('');
  $$('#chips .chip').forEach(c => c.onclick = () => setCode(SAMPLES[+c.dataset.i].kod, +c.dataset.i));
}

// ------------------------------------------------------------------ analiz
async function analyse() {
  if (cur.busy) return;
  const kod = ta().value, btn = $('#an');
  cur.busy = true; btn.disabled = true;
  $('#anTxt').textContent = engine === 'ready' ? t().analysing : t().loadingBtn;
  try {
    const r = await motor({tip: 'analiz', kod});
    cur.result = r; cur.code = kod; cur.stale = ta().value !== kod;
    if (!r.hata) recordAnalysis(kod, r);
  } catch (e) {
    cur.result = {hata: t().fail, bulgular: [], duzeltmeler: [], fark: []}; cur.code = kod;
  } finally {
    cur.busy = false; btn.disabled = false; $('#anTxt').textContent = t().analyse;
  }
  paintEditor(); renderResult();
  if (matchMedia('(max-width: 980px)').matches && !$('#v-dene').hidden) $('.kpis').scrollIntoView({behavior: 'smooth', block: 'start'});
}

function score(B) {
  const c = s => B.filter(b => b.onem === s).length;
  return Math.max(0, 100 - 25 * c('yüksek') - 10 * c('orta') - 3 * c('bilgi'));
}
function renderKpis() {
  const r = cur.result, ok = r && !r.hata;
  const B = ok ? r.bulgular : [];
  const sc = ok ? score(B) : null;
  $('#kScore').textContent = ok ? sc : '—';
  $('#kFind').textContent = ok ? nf(B.length) : '—';
  $('#kHigh').textContent = ok ? nf(B.filter(b => b.onem === 'yüksek').length) : '—';
  $('#kFix').textContent = ok ? nf(r.duzeltmeler.length) : '—';
  const ring = $('#ring');
  ring.style.setProperty('--p', ok ? sc : 0);
  ring.className = 'ring' + (ok && sc < 50 ? ' low' : ok && sc < 80 ? ' mid' : '');
  $('.kpi.score').title = t().scoreTip;
  const nF = $('#nFind'), nX = $('#nFix');
  nF.hidden = !ok; nF.textContent = ok ? B.length : '';
  nX.hidden = !ok || !r.duzeltmeler.length; nX.textContent = ok ? r.duzeltmeler.length : '';
}
function renderResult() {
  renderKpis();
  renderFindings(); renderFix(); renderMeasureTab();
}
function staleNote() { return cur.stale ? `<div class="kept" style="background:var(--amber-tint);color:var(--amber-ink);margin-bottom:10px">${t().stale}</div>` : ''; }
function renderFindings() {
  const el = $('#t-bulgular'), r = cur.result;
  if (!r) { el.innerHTML = `<div class="empty">${t().startEmpty}</div>`; return; }
  if (r.hata) { el.innerHTML = `<div class="empty">${esc(r.hata)}</div>`; return; }
  if (!r.bulgular.length) { el.innerHTML = staleNote() + `<div class="empty">${t().none}</div>`; return; }
  el.innerHTML = staleNote() + r.bulgular.map((b, i) => `<button class="find" data-i="${i}">
      <span class="sev ${b.onem}">${t().sev[b.onem]}</span><h4>${esc(ruleTitle(b.kural, b.baslik))}</h4><span class="where">${t().line} ${b.satir}</span>
      <p>${esc(ruleAdvice(b.kural, b.oneri))}</p>
      <span class="meta"><span class="tag">${b.kural}</span>${isAuto(b.kural) ? `<span class="tag auto">${t().autoTag}</span>` : `<span class="tag">${t().adviceTag}</span>`}</span>
    </button>`).join('');
  $$('#t-bulgular .find').forEach(f => f.onclick = () => { if (!cur.stale) gotoLine(r.bulgular[+f.dataset.i].satir); });
}
function diffRows(rows) {
  const show = rows.map((x, i) => x.tur !== 'esit' || rows.slice(Math.max(0, i - 2), i + 3).some(y => y.tur !== 'esit'));
  let out = '', gap = false;
  rows.forEach((r, i) => {
    if (!show[i]) { if (!gap) { out += '<div class="ln gap">⋯</div>'; gap = true; } return; }
    gap = false;
    out += `<div class="ln ${r.tur}"><i>${r.tur === 'sil' ? '−' : r.tur === 'ekle' ? '+' : ''}</i><span>${esc(r.metin) || ' '}</span></div>`;
  });
  return out;
}
function renderFix() {
  const el = $('#t-duzeltme'), r = cur.result;
  if (!r || r.hata) { el.innerHTML = `<div class="empty">${t().startEmpty}</div>`; return; }
  if (!r.fark.length) { el.innerHTML = staleNote() + `<div class="empty">${t().noFix}</div>`; return; }
  el.innerHTML = staleNote() + `<div class="row">
      <button class="tbtn" id="copyFix">${t().copy}</button>
      <button class="tbtn" id="dlFix">${t().download}</button>
      <button class="tbtn" id="applyFix">${t().apply}</button></div>
    <div class="kept" style="margin-bottom:10px">${r.bicim_korundu ? t().kept : t().reformatted}</div>
    <div class="diff"><div class="code">${diffRows(r.fark)}</div></div>
    <div class="fixlist">${r.duzeltmeler.map(f => `<div><b>${f.kural}</b>${esc(LANG === 'en' ? FIX_EN[f.kural] || f.aciklama : f.aciklama)}</div>`).join('')}</div>`;
  $('#copyFix').onclick = async e => {
    try { await navigator.clipboard.writeText(r.duzeltilmis); e.target.textContent = t().copied; setTimeout(() => { e.target.textContent = t().copy; }, 1500); } catch (x) {}
  };
  $('#dlFix').onclick = () => download('duzeltilmis.py', r.duzeltilmis, 'text/x-python');
  $('#applyFix').onclick = () => { setCode(r.duzeltilmis, null); analyse(); };
}
function renderMeasureTab() {
  const el = $('#t-olcum'), sid = sampleId();
  if (!sid) {
    const sc = SAMPLES.map((s, i) => [s, i]).filter(([s]) => s.id);
    el.innerHTML = `<div class="empty">${t().notScenario}<div class="chips" style="margin-top:10px">${sc.map(([s, i]) =>
      `<button class="chip" data-i="${i}">${esc(LANG === 'en' ? s.en : s.tr)}</button>`).join('')}</div></div>`;
    $$('#t-olcum .chip').forEach(c => c.onclick = () => { setCode(SAMPLES[+c.dataset.i].kod, +c.dataset.i); switchTab('olcum'); });
    return;
  }
  const prev = (HIST.find(h => h.kod === ta().value) || {}).olcum;
  el.innerHTML = `<p style="font-size:14px;color:var(--ink2);margin-bottom:12px">${t().measureIntro}</p>
    <button class="go leaf" id="olcBtn" ${cur.measuring ? 'disabled' : ''}>${prev ? t().again : t().measure}</button>
    <div id="olcOut" aria-live="polite">${cur.measuring ? `<div class="checks"><span><span class="spin"></span>${t().measuring}</span></div>` : prev ? measureHtml(prev) : ''}</div>`;
  $('#olcBtn').onclick = measure;
}
function measureHtml(m) {
  const wb = Math.max(m.duzeltilmis_s / m.ozgun_s * 100, 0.4);
  const lab = (w, txt) => w > 72 ? `<em style="right:8px;color:#fff">${txt}</em>` : `<em style="left:calc(${w}% + 8px)">${txt}</em>`;
  return `<div style="margin-top:16px;border-top:1px solid var(--rule);padding-top:14px">
    <div class="mhero"><div class="x">${big(m.kat)}</div><span>${t().less}</span></div>
    <div class="bars">
      <div class="lab"><b>${t().orig}</b>${t().perReq}</div><div class="track"><i style="width:100%;background:var(--c-waste)"></i>${lab(100, fmtS(m.ozgun_s))}</div>
      <div class="lab"><b>${t().fixed}</b>${t().perReq}</div><div class="track"><i style="width:${wb}%;background:var(--c-fixed)"></i>${lab(wb, fmtS(m.duzeltilmis_s))}</div>
    </div>
    <div class="checks"><span class="ok">✓ ${t().same(m.cikti)}</span>${m.sorgu ? `<span>${t().queries(m.sorgu.ozgun, m.sorgu.duzeltilmis)}</span>` : ''}</div>
    <p class="fine">${t().fine}</p></div>`;
}
async function measure() {
  const sid = sampleId(), kod = ta().value;
  if (!sid || cur.measuring) return;
  cur.measuring = true; renderMeasureTab();
  try {
    const r = await motor({tip: 'olc', senaryo: sid});
    if (!r.esdeger) { cur.measuring = false; renderMeasureTab(); $('#olcOut').innerHTML = `<div class="checks">${t().notSame}</div>`; return; }
    if (!HIST.some(h => h.kod === kod)) {                 // ölçülen kod geçmişte yoksa önce analizini kaydet
      const a = await motor({tip: 'analiz', kod});
      if (!a.hata) recordAnalysis(kod, a);
    }
    recordMeasure(kod, r);
    cur.measuring = false; renderMeasureTab();
  } catch (e) {
    cur.measuring = false; renderMeasureTab(); $('#olcOut').innerHTML = `<div class="checks">${t().fail}</div>`;
  }
}
function switchTab(name) {
  cur.tab = name;
  $$('.rtabs button').forEach(b => b.setAttribute('aria-selected', b.dataset.t === name));
  ['bulgular', 'duzeltme', 'olcum'].forEach(x => { $('#t-' + x).hidden = x !== name; });
}

// ------------------------------------------------------------------ Analizler
function filteredHist() {
  const q = ($('#q').value || '').toLocaleLowerCase('tr');
  const k = $('#fRule').value;
  return HIST.filter(h => (!q || histLabel(h).toLocaleLowerCase('tr').includes(q) || h.kod.toLocaleLowerCase('tr').includes(q)) &&
                          (!k || h.bulgular.some(b => b.kural === k)));
}
function renderHistory() {
  const H = HIST;
  $('#sCount').textContent = nf(H.length);
  $('#sFind').textContent = nf(H.reduce((a, h) => a + h.bulgular.length, 0));
  $('#sFix').textContent = nf(H.reduce((a, h) => a + h.duzeltme, 0));
  const ks = H.filter(h => h.olcum).map(h => h.olcum.kat).sort((a, b) => a - b);
  $('#sMeas').textContent = ks.length ? big(ks.length % 2 ? ks[(ks.length - 1) / 2] : Math.sqrt(ks[ks.length / 2 - 1] * ks[ks.length / 2])) : '—';
  $('#q').placeholder = t().search;
  const sel = $('#fRule'), was = sel.value;
  sel.innerHTML = `<option value="">${t().allRules}</option>` + RULES.map(r => `<option value="${r.kural}">${r.kural} · ${esc(ruleTitle(r.kural))}</option>`).join('');
  sel.value = was;
  renderRuleChart(); renderMeasChart(); renderTable();
}
function renderRuleChart() {
  const cnt = {}, an = {};
  for (const h of HIST) {
    const seen = new Set();
    for (const b of h.bulgular) { cnt[b.kural] = (cnt[b.kural] || 0) + 1; if (!seen.has(b.kural)) { an[b.kural] = (an[b.kural] || 0) + 1; seen.add(b.kural); } }
  }
  const rows = Object.entries(cnt).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  if (!rows.length) { $('#chRules').innerHTML = `<div class="empty" style="margin-top:14px">${t().noData}</div>`; return; }
  const max = rows[0][1];
  $('#chRules').innerHTML = `<div class="hb">${rows.map(([k, n]) =>
    `<div class="nm"><b>${k}</b>${esc(ruleTitle(k))}</div><div class="tr hit" data-tip="${esc(`<b>${k} · ${ruleTitle(k)}</b>${t().times(n, an[k])}`)}"><i style="width:${n / max * 100}%;background:var(--c-waste)"></i></div><div class="v">${nf(n)}</div>`).join('')}</div>`;
  bindTips('#chRules');
}
function renderMeasChart() {
  const M = HIST.filter(h => h.olcum);
  if (!M.length) { $('#chMeas').innerHTML = `<div class="empty" style="margin-top:14px">${t().noMeas}</div>`; return; }
  const top = Math.max(1, Math.ceil(Math.log10(Math.max(...M.map(h => h.olcum.kat), 10))));
  const w = k => Math.max(Math.log10(Math.max(k, 1)) / top * 100, 1);
  const ticks = Array.from({length: top + 1}, (_, i) => nf(10 ** i) + '×');
  $('#chMeas').innerHTML = `<div class="hb">${M.map(h => {
    const o = h.olcum;
    const tip = `<b>${esc(histLabel(h))}: ${big(o.kat)}</b>${fmtS(o.ozgun_s)} → ${fmtS(o.duzeltilmis_s)}<br>${new Date(o.t).toLocaleString(LANG === 'en' ? 'en-GB' : 'tr-TR')}`;
    return `<div class="nm">${esc(histLabel(h))}</div><div class="tr hit" data-tip="${esc(tip)}"><i style="width:${w(o.kat)}%;background:var(--c-fixed)"></i></div><div class="v">${big(o.kat)}</div>`;
  }).join('')}<div class="nm"></div><div class="ticks">${ticks.map((x, i) => `<span style="left:${i / top * 100}%">${x}</span>`).join('')}</div><div class="v"></div></div>`;
  bindTips('#chMeas');
}
function renderTable() {
  const box = $('#histBody');
  if (!HIST.length) { box.innerHTML = `<div style="padding:16px"><div class="empty">${t().histEmpty} <a class="tbtn" href="#dene" style="margin-left:8px">${t().goDash}</a></div></div>`; return; }
  const rows = filteredHist();
  if (!rows.length) { box.innerHTML = `<div style="padding:16px"><div class="empty">${t().noMatch}</div></div>`; return; }
  const c = t().cols;
  box.innerHTML = `<table class="ht"><thead><tr>${c.map((x, i) => `<th${i >= 3 && i <= 4 ? ' style="text-align:right"' : ''}>${x}</th>`).join('')}</tr></thead><tbody>${rows.map(h => {
    const by = {};
    for (const b of h.bulgular) { by[b.kural] = by[b.kural] || {n: 0, s: b.onem}; by[b.kural].n++; }
    const tags = Object.entries(by).map(([k, v]) => `<span class="sev ${v.s}" title="${esc(ruleTitle(k))}">${k}${v.n > 1 ? ' ×' + v.n : ''}</span>`).join('') || `<span class="tag">—</span>`;
    return `<tr data-id="${h.id}">
      <td class="t">${new Date(h.t).toLocaleString(LANG === 'en' ? 'en-GB' : 'tr-TR', {dateStyle: 'short', timeStyle: 'short'})}</td>
      <td class="nm">${esc(histLabel(h))}<small>${t().lines(h.satir)}</small></td>
      <td class="tagc"><div class="tags">${tags}</div></td>
      <td class="num" data-l="${c[3]}">${nf(h.duzeltme)}</td>
      <td class="num" data-l="${c[4]}">${h.olcum ? big(h.olcum.kat) : '—'}</td>
      <td class="acts"><div><button data-a="open">${t().open}</button><button data-a="del">${t().del}</button></div></td></tr>`;
  }).join('')}</tbody></table>`;
  $$('#histBody button').forEach(b => b.onclick = () => {
    const id = b.closest('tr').dataset.id, h = HIST.find(x => x.id === id);
    if (!h) return;
    if (b.dataset.a === 'del') { HIST = HIST.filter(x => x.id !== id); saveHist(); renderHistory(); return; }
    const s = SAMPLES.findIndex(x => x.kod === h.kod);
    setCode(h.kod, s >= 0 ? s : null);
    location.hash = '#dene';
    analyse();
  });
}
function bindTips(root) {
  const tip = $('#tip');
  $$(root + ' .hit').forEach(el => {
    el.onmousemove = e => {
      tip.innerHTML = el.dataset.tip; tip.hidden = false;
      const x = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
      tip.style.left = x + 'px'; tip.style.top = (e.clientY + 14) + 'px';
    };
    el.onmouseleave = () => { tip.hidden = true; };
  });
}
function download(name, text, type) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], {type}));
  a.download = name; document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
}
function exportCsv() {
  const sep = LANG === 'tr' ? ';' : ',';
  const q = v => /["\n;,]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v);
  const head = LANG === 'tr' ? ['tarih', 'ad', 'satir', 'bulgu', 'yuksek', 'kurallar', 'duzeltme', 'olcum_kat'] : ['date', 'name', 'lines', 'findings', 'high', 'rules', 'fixes', 'measured_gain'];
  const rows = HIST.map(h => [h.t, histLabel(h), h.satir, h.bulgular.length, h.bulgular.filter(b => b.onem === 'yüksek').length,
    [...new Set(h.bulgular.map(b => b.kural))].join(' '), h.duzeltme, h.olcum ? h.olcum.kat.toFixed(2) : ''].map(q).join(sep));
  download('yesil-kod-analizler.csv', '﻿' + [head.join(sep), ...rows].join('\n'), 'text/csv');
}

// ------------------------------------------------------------------ Kurallar
let ruleCat = '', ruleQ = '', ruleSort = 'kod', ENV = null;
const RD = {
  tr: {
    back: '← Bütün kurallar', why: 'Neden enerji harcar?', when: 'Ne zaman sorun değil?', cx: 'Yapılan iş', bad: 'İsraflı', good: 'Verimli',
    engine: 'Motorun yazdığı (israflı örnekten, kendiliğinden)', engineOk: k => `Motorun düzeltmesi de aynı girdiyle sınandı: çıktı aynı, ${k}.`,
    source: 'Kaynak', related: 'Aynı gruptan', measured: 'Ölçüm', notMeasured: 'Neden ölçülmedi?',
    same: 'İki sürüm aynı girdiyle birebir aynı sonucu verdi.', random: 'Çıktı rastgele olduğu için karşılaştırılmadı; yalnızca süre ölçüldü.',
    faster: 'daha kısa sürede', lessCpu: 'daha az işlemci süresi', lessMem: 'daha az bellek', noDiff: 'süre farkı yok', slower: 'iyi sürüm bu kadar yavaş',
    rows: ['Süre (çağrı başına)', 'İşlemci süresi', 'Bellek tepe değeri', 'Yazılan dosya'], ratio: 'Oran',
    meta: e => `${e.islemci || e.sistem} · Python ${e.python} · ${dateTxt(e.tarih)} · ${e.tur} turun ortancası`,
    device: 'Bu cihazda ölç', deviceRun: 'Ölçülüyor…', deviceAgain: 'Tekrar ölç', onDevice: 'Bu cihazda', onMac: m => `Mac’te: ${m}`,
    noBrowser: 'Bu kural tarayıcıda ölçülemez (iş parçacığı, alt süreç ya da diske eşitleme gerektirir); sonuç Mac’te alındı.',
    pkg: p => `İlk ölçümde ${p} indirilir.`, skipped: 'Bu cihazda ölçülemedi', tryBad: 'İsraflı örneği Dashboard’da dene', tryGood: 'Verimli örneği Dashboard’da dene',
    detail: 'Ayrıntı', gain: {win: k => `${k} hızlı`, cpu: k => `${k} az işlemci`, mem: k => `${k} az bellek`, flat: 'fark yok', loss: k => `${k} yavaş`, na: 'ölçülmedi'},
    sort: [['kod', 'Koda göre'], ['kazanc', 'Ölçülen kazanca göre'], ['onem', 'Öneme göre']],
    summary: (n, eq, rnd, un) => `${nf(n)} kural ölçüldü. Çıktısı karşılaştırılabilen ${nf(eq)} kuralın hepsinde iki sürüm birebir aynı sonucu verdi${rnd ? `; ${nf(rnd)} kuralın çıktısı rastgele` : ''}. ${nf(un)} kural veritabanı sunucusu, GPU ya da ağ gerektirdiği için ölçülmedi.`,
  },
  en: {
    back: '← All rules', why: 'Why does it waste energy?', when: 'When is it fine?', cx: 'Work done', bad: 'Wasteful', good: 'Efficient',
    engine: 'What the engine wrote (from the wasteful example, on its own)', engineOk: k => `The engine’s fix was tested on the same input too: same output, ${k}.`,
    source: 'Source', related: 'Same group', measured: 'Measurement', notMeasured: 'Why was it not measured?',
    same: 'Both versions gave exactly the same result on the same input.', random: 'The output is random, so it was not compared; only time was measured.',
    faster: 'less time', lessCpu: 'less CPU time', lessMem: 'less memory', noDiff: 'no time difference', slower: 'the good version is this much slower',
    rows: ['Time (per call)', 'CPU time', 'Peak memory', 'File written'], ratio: 'Ratio',
    meta: e => `${e.islemci || e.sistem} · Python ${e.python} · ${dateTxt(e.tarih)} · median of ${e.tur} rounds`,
    device: 'Measure on this device', deviceRun: 'Measuring…', deviceAgain: 'Measure again', onDevice: 'On this device', onMac: m => `On the Mac: ${m}`,
    noBrowser: 'This rule cannot be measured in a browser (it needs threads, a subprocess or a disk sync); the result was taken on the Mac.',
    pkg: p => `${p} is downloaded on the first measurement.`, skipped: 'Could not be measured on this device', tryBad: 'Try the wasteful example in the Dashboard', tryGood: 'Try the efficient example in the Dashboard',
    detail: 'Details', gain: {win: k => `${k} faster`, cpu: k => `${k} less CPU`, mem: k => `${k} less memory`, flat: 'no difference', loss: k => `${k} slower`, na: 'not measured'},
    sort: [['kod', 'By code'], ['kazanc', 'By measured gain'], ['onem', 'By severity']],
    summary: (n, eq, rnd, un) => `${nf(n)} rules were measured. In all ${nf(eq)} whose output could be compared, both versions gave exactly the same result${rnd ? `; ${nf(rnd)} has a random output` : ''}. ${nf(un)} rules need a database server, a GPU or the network, so they were not measured.`,
  },
};
const rd = () => RD[LANG];
const rtx = (r, a) => LANG === 'en' ? r[a + '_en'] : r[a];
const dateTxt = d => new Date(d + 'T12:00:00').toLocaleDateString(LANG === 'en' ? 'en-GB' : 'tr-TR', {day: 'numeric', month: 'long', year: 'numeric'});
const fmtB = b => b >= 1048576 ? nf(b / 1048576, 1) + ' MB' : b >= 1024 ? nf(b / 1024, 1) + ' KB' : nf(b) + ' B';
function gainOf(o) {
  if (!o) return {cls: 'na'};
  if (o.kat >= 1.1) return {cls: o.olcut === 'islemci' ? 'cpu' : 'win', k: o.kat};
  if (o.bellek_kat >= 2 && o.kotu.bellek_b - o.iyi.bellek_b >= 4096) return {cls: 'mem', k: o.bellek_kat};   // birkaç düzine baytlık fark kazanç sayılmaz
  if (o.kat > 0.9) return {cls: 'flat', k: o.kat};
  return {cls: 'loss', k: 1 / o.kat};
}
function gainChip(r) {
  const g = gainOf(r.olcum), f = rd().gain[g.cls];
  return `<span class="gain ${g.cls}">${typeof f === 'function' ? f(big(g.k)) : f}</span>`;
}
const SEV_ORDER = {'yüksek': 0, 'orta': 1, 'bilgi': 2};
function renderRules() {
  const n = RULES.length, auto = RULES.filter(r => r.otomatik).length;
  const chips = [['', LANG === 'en' ? `All ${n}` : `Tümü (${n})`]].concat(Object.entries(CATS).map(([k, v]) =>
    [k, `${v[LANG]} (${RULES.filter(r => r.kategori === k).length})`]));
  $('#ruleCats').innerHTML = chips.map(([k, l]) => `<button class="chip" data-c="${k}" aria-pressed="${k === ruleCat}">${esc(l)}</button>`).join('') +
    `<span class="tag auto" style="align-self:center">${LANG === 'en' ? `${auto} fixed automatically` : `${auto} tanesini motor düzeltir`}</span>`;
  $$('#ruleCats .chip').forEach(c => c.onclick = () => { ruleCat = c.dataset.c; renderRules(); });
  $('#ruleSort').innerHTML = rd().sort.map(([v, l]) => `<option value="${v}"${v === ruleSort ? ' selected' : ''}>${l}</option>`).join('');
  const olc = RULES.filter(r => r.olcum);
  $('#ruleMeta').innerHTML = olc.length ? esc(rd().summary(olc.length, olc.filter(r => r.olcum.esdeger === true).length,
    olc.filter(r => r.olcum.esdeger === null).length, n - olc.length)) + (ENV ? `<br><span>${esc(rd().meta(ENV))}</span>` : '') : '';
  const q = ruleQ.toLocaleLowerCase('tr');
  let shown = RULES.filter(r => (!ruleCat || r.kategori === ruleCat) && (!q ||
    [r.kural, r.baslik, r.baslik_en, r.oneri, r.oneri_en, r.kaynak].join(' ').toLocaleLowerCase('tr').includes(q)));
  if (ruleSort === 'kazanc') shown = shown.slice().sort((a, b) => ((b.olcum || {}).kat || 0) - ((a.olcum || {}).kat || 0));
  if (ruleSort === 'onem') shown = shown.slice().sort((a, b) => SEV_ORDER[a.onem] - SEV_ORDER[b.onem]);
  $('#ruleCount').textContent = LANG === 'en' ? `${shown.length} shown` : `${shown.length} kural gösteriliyor`;
  $('#rules').innerHTML = shown.map(r => `<div class="card rule">
      <div class="cat">${esc((CATS[r.kategori] || {})[LANG] || '')}</div>
      <div class="rh"><b>${r.kural}</b><span class="sev ${r.onem}">${t().sev[r.onem]}</span>${r.otomatik ? `<span class="tag auto">${t().autoFix}</span>` : `<span class="tag">${t().advice}</span>`}${gainChip(r)}</div>
      <h3><a href="#kural/${r.kural}">${esc(ruleTitle(r.kural))}</a></h3><p>${esc(ruleAdvice(r.kural, r.oneri))}</p>
      <pre>${esc(r.ornek.trim())}</pre>
      <div class="src">${LANG === 'en' ? 'Source' : 'Kaynak'}: ${esc(r.kaynak)}</div>
      <div class="row" style="margin:0"><a class="tbtn" href="#kural/${r.kural}">${rd().detail} →</a><button class="tbtn" data-k="${r.kural}">${t().tryIt}</button></div></div>`).join('');
  $$('#rules button.tbtn').forEach(b => b.onclick = () => tryCode(ruleOf(b.dataset.k).ornek));
}
function tryCode(kod) { setCode(kod, null); location.hash = '#dene'; analyse(); }
function codeBox(title, cls, src, other) {
  const diger = new Set(other.split('\n').map(s => s.trim()));
  const satirlar = src.replace(/\n+$/, '').split('\n');
  return `<div class="cbox ${cls}"><div class="chd">${title}</div><pre>${satirlar.map(l =>
    `<span${l.trim() && !diger.has(l.trim()) ? ' class="chg"' : ''}>${esc(l) || ' '}</span>`).join('')}</pre></div>`;
}
function ruleBars(A, B, key) {
  const f = key === 'bellek_b' ? fmtB : fmtS, max = Math.max(A[key], B[key]) || 1;
  const lab = (w, txt) => w > 72 ? `<em style="right:8px;color:#fff">${txt}</em>` : `<em style="left:calc(${w}% + 8px)">${txt}</em>`;
  return `<div class="bars">${[[rd().bad, A[key], 'var(--c-waste)'], [rd().good, B[key], 'var(--c-fixed)']].map(([l, v, c]) => {
    const w = Math.max(v / max * 100, 0.4);
    return `<div class="lab"><b>${l}</b></div><div class="track"><i style="width:${w}%;background:${c}"></i>${lab(w, f(v))}</div>`;
  }).join('')}</div>`;
}
function ruleMeasureHtml(r) {
  const L = rd(), o = r.olcum;
  if (!o) return `<h2>${L.notMeasured}</h2><p>${esc(rtx(r, 'olculmedi'))}</p>`;
  const g = gainOf(o), A = o.kotu, B = o.iyi;
  const hero = {win: [big(o.kat), L.faster], cpu: [big(o.kat), L.lessCpu], mem: [big(o.bellek_kat), L.lessMem],
                flat: ['≈ 1×', L.noDiff], loss: [big(1 / o.kat), L.slower]}[g.cls];
  const key = g.cls === 'mem' ? 'bellek_b' : g.cls === 'cpu' ? 'islemci_s' : 'sure_s';
  const rows = [[L.rows[0], 'sure_s', fmtS], [L.rows[1], 'islemci_s', fmtS], [L.rows[2], 'bellek_b', fmtB]];
  if (A.boyut_b) rows.push([L.rows[3], 'boyut_b', fmtB]);
  const oran = (a, b) => b ? big(a / b) : '—';
  const pk = r.tanim && /\b(import|from)\s+pandas\b/.test(r.ornek + r.iyi + (r.tanim.hazirla || '')) ? 'pandas + NumPy (~20 MB)'
    : r.tanim && /\b(import|from)\s+numpy\b/.test(r.ornek + r.iyi + (r.tanim.hazirla || '')) ? 'NumPy (~8 MB)' : '';
  return `<h2>${L.measured}</h2>
    <div class="mhero"><div class="x ${g.cls}">${hero[0]}</div><span>${hero[1]}</span></div>
    ${ruleBars(A, B, key)}
    <table class="mt"><thead><tr><th></th><th>${L.bad}</th><th>${L.good}</th><th>${L.ratio}</th></tr></thead><tbody>
      ${rows.map(([l, k, f]) => `<tr${k === key ? ' class="on"' : ''}><th>${l}</th><td>${f(A[k] || 0)}</td><td>${f(B[k] || 0)}</td><td>${oran(A[k], B[k])}</td></tr>`).join('')}
    </tbody></table>
    <div class="checks"><span class="${o.esdeger ? 'ok' : ''}">${o.esdeger ? '✓ ' + L.same : L.random}</span></div>
    ${rtx(o, 'not') ? `<p class="note">${esc(rtx(o, 'not'))}</p>` : ''}
    ${ENV ? `<p class="fine">${esc(L.meta(ENV))}</p>` : ''}
    <div class="dev">${r.tanim ? `<button class="go leaf" id="devGo">${L.device}</button>${pk ? `<span class="pk">${L.pkg(pk)}</span>` : ''}<div id="devRes" aria-live="polite"></div>`
      : `<p class="fine">${L.noBrowser}</p>`}</div>`;
}
function devHtml(m, r) {
  const L = rd();
  if (m.atlandi) return `<p class="note">${L.skipped}: ${esc(m.atlandi)}</p>`;
  if (m.esdeger === false) return `<p class="note">${t().notSame}</p>`;
  const g = gainOf(m), f = L.gain[g.cls === 'na' ? 'flat' : g.cls];
  return `<div class="devr"><b>${L.onDevice}: ${typeof f === 'function' ? f(big(g.k)) : f}</b>
    <span>${L.bad} ${fmtS(m.kotu.sure_s)} · ${L.good} ${fmtS(m.iyi.sure_s)}${m.esdeger ? ' · ✓' : ''}</span>
    <span>${L.onMac(gainChip(r).replace(/<[^>]+>/g, ''))}</span></div>`;
}
function renderRuleDetail(k) {
  const r = ruleOf(k), d = $('#ruleDetail');
  $('#ruleList').hidden = !!r; d.hidden = !r;
  if (!r) { renderRules(); return; }
  const L = rd(), cat = (CATS[r.kategori] || {})[LANG] || '', i = RULES.indexOf(r), prev = RULES[i - 1], next = RULES[i + 1];
  const m = r.olcum && r.olcum.motor;
  document.title = `${r.kural} · ${ruleTitle(r.kural)} · Yeşil Kod`;
  d.innerHTML = `
    <nav class="rd-nav"><a href="#kurallar" class="tbtn">${L.back}</a><span class="sp"></span>
      ${prev ? `<a class="tbtn" href="#kural/${prev.kural}" aria-label="${prev.kural}">← ${prev.kural}</a>` : ''}
      ${next ? `<a class="tbtn" href="#kural/${next.kural}" aria-label="${next.kural}">${next.kural} →</a>` : ''}</nav>
    <header class="rd-head">
      <div class="rh"><span class="cat">${esc(cat)}</span><b>${r.kural}</b><span class="sev ${r.onem}">${t().sev[r.onem]}</span>${r.otomatik ? `<span class="tag auto">${t().autoFix}</span>` : `<span class="tag">${t().advice}</span>`}</div>
      <h1>${esc(ruleTitle(r.kural))}</h1>
      <p class="lead">${esc(ruleAdvice(r.kural, r.oneri))}</p>
    </header>
    <div class="rd-grid">
      <section class="card rd-m">${ruleMeasureHtml(r)}</section>
      <div class="rd-side">
        <section class="card"><h2>${L.why}</h2><p>${esc(rtx(r, 'neden'))}</p>
          <div class="cx"><span>${L.cx}</span><b>${esc(rtx(r, 'karmasiklik'))}</b></div></section>
        <section class="card"><h2>${L.when}</h2><p>${esc(rtx(r, 'istisna'))}</p></section>
        <section class="card"><h2>${L.source}</h2><p><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.kaynak)} ↗</a></p>
          <p class="url">${esc(r.url.replace(/^https?:\/\//, ''))}</p></section>
      </div>
    </div>
    <section class="rd-code">
      <div class="codes">${codeBox(L.bad, 'bad', r.ornek, r.iyi)}${codeBox(L.good, 'good', r.iyi, r.ornek)}</div>
      ${r.duzeltilmis ? `<div class="codes one">${codeBox(L.engine, 'eng', r.duzeltilmis, r.ornek)}</div>
        ${m && m.esdeger ? `<p class="kept">✓ ${esc(L.engineOk(big(m.kat)))}</p>` : ''}` : ''}
      <div class="row" style="margin-top:12px"><button class="tbtn" data-try="ornek">${L.tryBad} →</button><button class="tbtn" data-try="iyi">${L.tryGood} →</button></div>
    </section>
    <section class="rd-rel"><h2>${L.related} · ${esc(cat)}</h2><div class="rel">${RULES.filter(x => x.kategori === r.kategori && x !== r).map(x =>
      `<a href="#kural/${x.kural}"><b>${x.kural}</b><span>${esc(ruleTitle(x.kural))}</span>${gainChip(x)}</a>`).join('')}</div></section>`;
  $$('#ruleDetail [data-try]').forEach(b => b.onclick = () => tryCode(r[b.dataset.try]));
  const go = $('#devGo');
  if (go) go.onclick = async () => {
    go.disabled = true; go.innerHTML = `<span class="spin"></span>${L.deviceRun}`;
    let html;
    try { html = devHtml(await motor({tip: 'kural', kod: r.kural, kotu: r.ornek, iyi: r.iyi, tanim: r.tanim}), r); }
    catch (e) { html = `<p class="note">${t().fail}</p>`; }
    if (!document.body.contains(go)) return;               // bu arada başka kurala geçildi
    $('#devRes').innerHTML = html; go.disabled = false; go.textContent = rd().deviceAgain;
  };
}

// ------------------------------------------------------------------ dil ve yönlendirme
function setLang(l) {
  LANG = l; document.documentElement.lang = l; document.body.classList.toggle('en', l === 'en');
  $$('.lang button').forEach(b => b.setAttribute('aria-pressed', b.dataset.l === l));
  const tr = $('#vid') && $('#vid').textTracks[0];
  if (tr) tr.mode = l === 'en' ? 'showing' : 'hidden';
  $('#privacy').textContent = t().privacy;
  $('#anKey').textContent = IS_MAC ? '⌘↵' : 'Ctrl+↵';
  setEngine(engine); renderChips(); paintEditor(); renderResult();
  if (!$('#v-analizler').hidden) renderHistory();
  $('#ruleQ').placeholder = l === 'en' ? 'Search code, title or source' : 'Kodda, başlıkta ya da kaynakta ara';
  if (!$('#v-kurallar').hidden) route();
  try { localStorage.setItem('yk-lang', l); } catch (e) {}
}
function route() {
  const h = decodeURIComponent(location.hash.slice(1));
  const kural = (/^kural\/(YK\d{3})$/i.exec(h) || [])[1];
  const v = kural ? 'kurallar' : VIEWS.includes(h) ? h : 'proje';
  document.title = BASE_TITLE;
  VIEWS.forEach(x => { $('#v-' + x).hidden = x !== v; });
  $$('.nav a').forEach(a => { if (a.dataset.v === v) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
  if (v === 'proje') {
    const el = h && h !== 'proje' && document.getElementById(h);
    if (el) el.scrollIntoView(); else window.scrollTo(0, 0);
  } else window.scrollTo(0, 0);
  if (v === 'dene') { warmUp(); paintEditor(); }
  if (v === 'analizler') renderHistory();
  if (v === 'kurallar') {
    if (kural) renderRuleDetail(kural.toUpperCase());
    else { $('#ruleDetail').hidden = true; $('#ruleList').hidden = false; renderRules(); }
  }
}

// ------------------------------------------------------------------ başlangıç
(async () => {
  let l = 'tr';
  try { l = localStorage.getItem('yk-lang') || ((navigator.language || '').toLowerCase().startsWith('tr') ? 'tr' : 'en'); } catch (e) {}
  if (/[?&]lang=en/.test(location.search)) l = 'en';
  if (/[?&]lang=tr/.test(location.search)) l = 'tr';
  loadHist(); updateNavCount();
  try {
    const [o, k] = await Promise.all(['py/ornekler.json', 'py/kurallar.json'].map(u => fetch(u).then(r => r.json())));
    SAMPLES = o; RULES = k.kurallar; CATS = k.kategoriler; ENV = k.olcum_ortami || null;
  } catch (e) {}
  ta().value = SAMPLES.length ? SAMPLES[0].kod : '';
  cur.sample = SAMPLES.length ? 0 : null;
  cur.autoRun = location.hash === '#dene';                 // QR'dan gelen ziyaretçi: motor hazır olunca örnek kendiliğinden analiz edilsin
  ta().addEventListener('input', onInput);
  ta().addEventListener('keydown', onKey);
  ta().addEventListener('scroll', syncScroll);
  $('#an').onclick = analyse;
  $('#clear').onclick = () => { setCode('', null); ta().focus(); };
  $('#file').onchange = e => {
    const f = e.target.files[0]; if (!f) return;
    f.text().then(txt => setCode(txt.replace(/\r\n?/g, '\n'), null), () => alert(t().fileErr));
    e.target.value = '';
  };
  $$('.rtabs button').forEach(b => b.onclick = () => switchTab(b.dataset.t));
  $('#q').oninput = renderTable;
  $('#ruleQ').oninput = e => { ruleQ = e.target.value; renderRules(); };
  $('#ruleSort').onchange = e => { ruleSort = e.target.value; renderRules(); };
  $('#fRule').onchange = renderTable;
  $('#expJson').onclick = () => download('yesil-kod-analizler.json', JSON.stringify(HIST, null, 1), 'application/json');
  $('#expCsv').onclick = exportCsv;
  $('#clearAll').onclick = () => { if (HIST.length && confirm(t().confirmAll)) { HIST = []; saveHist(); renderHistory(); } };
  $$('.lang button').forEach(b => b.onclick = () => setLang(b.dataset.l));
  window.addEventListener('hashchange', route);
  window.addEventListener('storage', e => { if (e.key === KEY) { loadHist(); updateNavCount(); if (!$('#v-analizler').hidden) renderHistory(); } });
  setLang(l);
  route();
})();
