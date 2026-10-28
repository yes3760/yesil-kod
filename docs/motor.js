// Yeşil Kod motoru (Web Worker). Standdaki Python motorunun aynısını Pyodide ile
// telefonda çalıştırır; sayfa donmasın diye ayrı iş parçacığındadır.
//   {tip: "analiz", kod}     statik analiz + biçimi koruyan düzeltme (kod çalıştırılmaz)
//   {tip: "olc", senaryo}    hazır senaryonun iki sürümünü çalıştırır, karşılaştırır, süreleri ölçer
importScripts("https://cdn.jsdelivr.net/pyodide/v0.27.2/full/pyodide.js");

const DOSYALAR = ["__init__.py", "config.py", "kurallar.py", "analyzer.py", "fixer.py", "meter.py", "proof.py", "scenarios.py"];
let hazir = null, sqlite = null;

function baslat() {
  if (!hazir) hazir = (async () => {
    const py = await loadPyodide();
    py.FS.mkdirTree("/home/pyodide/greencode");
    for (const f of DOSYALAR) {
      const r = await fetch("py/greencode/" + f);
      if (!r.ok) throw new Error(f + " yüklenemedi");
      py.FS.writeFile("/home/pyodide/greencode/" + f, await r.text());
    }
    py.runPython(`
import sys, json, time
sys.path.insert(0, "/home/pyodide")
from greencode import analyzer, fixer

def yesil(kod):
    r = analyzer.analyze(kod)
    r["fark"], r["duzeltmeler"], r["bicim_korundu"], r["duzeltilmis"] = [], [], False, None
    if not r["hata"]:
        try:
            new, orig, fixes = fixer.fix(kod)
            if fixes:
                r["fark"] = fixer.side_by_side(orig, new)
                r["duzeltmeler"] = [f.to_dict() for f in fixes]
                r["bicim_korundu"] = fixer.fix.bicim_korundu
                r["duzeltilmis"] = new
        except Exception as e:
            r["duzeltme_hatasi"] = str(e)
    return json.dumps(r, ensure_ascii=False)

_veri = None

def _ort(fn, bir, butce, ust):
    """fn'i bütçe kadar tekrarlayıp bir çağrının ortalama süresini döndürür."""
    k = max(1, min(ust, int(butce / max(bir, 1e-6))))
    t0 = time.perf_counter()
    for _ in range(k):
        fn()
    return (time.perf_counter() - t0) / k, k

def olc(sid):
    global _veri
    from greencode import proof, scenarios
    if _veri is None:
        _veri = scenarios.build_data()
    s = scenarios.get(sid)
    run_a, run_b, *_ = proof.prepare(s["kod"], s["giris"], _veri)
    ns_a, ns_b = proof.prepare.last_ns
    t0 = time.perf_counter(); a = run_a(); ta = time.perf_counter() - t0
    t0 = time.perf_counter(); b = run_b(); tb = time.perf_counter() - t0
    if proof._norm(a) != proof._norm(b):
        return json.dumps({"esdeger": False})
    sorgu = None
    if ns_a["DB"].count:
        sorgu = {"ozgun": ns_a["DB"].count, "duzeltilmis": ns_b["DB"].count}
    ma, ka = _ort(run_a, ta, 1.2, 50)
    mb, kb = _ort(run_b, tb, 0.6, 20000)
    return json.dumps({"esdeger": True, "cikti": len(a), "ozgun_s": ma, "duzeltilmis_s": mb,
                       "kat": ma / mb if mb else None, "tekrar": [ka, kb], "sorgu": sorgu})
`);
    return py;
  })().catch(e => { hazir = null; throw e; });
  return hazir;
}

onmessage = async e => {
  const {id, tip} = e.data;
  try {
    const py = await baslat();
    let sonuc = true;
    if (tip === "analiz") {
      sonuc = JSON.parse(py.globals.get("yesil")(e.data.kod));
    } else if (tip === "olc") {
      if (!sqlite) sqlite = py.loadPackage("sqlite3").catch(err => { sqlite = null; throw err; });
      await sqlite;
      sonuc = JSON.parse(py.globals.get("olc")(e.data.senaryo));
    }
    postMessage({id, ok: true, sonuc});
  } catch (err) {
    postMessage({id, ok: false, hata: String((err && err.message) || err)});
  }
};
