"""Kural kanıtı: bir kuralın kötü ve iyi örneğini aynı girdiyle çalıştırır.

1. İki sürümün çıktısı (ya da bıraktığı iz: dosya, veritabanı, ekran çıktısı)
   karşılaştırılır. Aynı değilse ölçüm yapılmaz.
2. Süre ve işlemci süresi iki sürüm sırayla (A, B, A, B, ...) ölçülerek alınır;
   makinenin anlık yükü iki tarafı eşit etkiler. Sonuç turların ortancasıdır.
3. Bellek tepe değeri tracemalloc ile ayrı bir çalıştırmada ölçülür.

Her sürüm kendi geçici klasöründe çalışır; örneklerdeki göreli dosya yolları
("veri.db", "gelen/") oraya düşer. Ölçüm tanımları ornekler/kurallar/olcum.py
içindedir. Aynı kod sitede tarayıcıda (Pyodide) da çalışır.
"""
from __future__ import annotations

import ast
import contextlib
import io
import math
import os
import platform
import random
import shutil
import sqlite3
import statistics
import sys
import tempfile
import time
import tracemalloc
import warnings

from . import config

try:                    # tarayıcıda (Pyodide) işlemci saati olmayabilir; o zaman duvar saati
    time.process_time()
    _islemci_saati = time.process_time
except (OSError, AttributeError):
    _islemci_saati = time.perf_counter

TUR = 5                 # her sürüm için ölçüm turu
TUR_SURESI = 0.06       # bir turun hedef süresi (s)

ADLAR = ["Ayşe", "Mehmet", "Zeynep", "Mustafa", "Elif", "Ahmet", "Fatma", "Emre",
         "Yunus", "Zahid", "Deniz", "Ece", "Can", "Selin", "Burak", "Merve"]
SOYADLAR = ["Yılmaz", "Kaya", "Demir", "Şahin", "Çelik", "Yıldız", "Aydın", "Öztürk",
            "Arslan", "Doğan", "Kılıç", "Aslan", "Çetin", "Kara", "Koç", "Kurt"]
SEHIRLER = ["Adana", "Ankara", "Antalya", "Bursa", "Diyarbakır", "Erzurum", "Eskişehir",
            "Gaziantep", "İstanbul", "İzmir", "Kayseri", "Konya", "Malatya", "Mersin",
            "Sakarya", "Samsun", "Trabzon", "Van"]

_SEMA = """
CREATE TABLE musteri (id INTEGER PRIMARY KEY, ad TEXT, sehir TEXT, eposta TEXT, adres TEXT, notlar TEXT);
CREATE INDEX musteri_sehir ON musteri (sehir);
CREATE TABLE siparis (id INTEGER PRIMARY KEY, musteri_id INTEGER, tutar INTEGER, tarih TEXT);
CREATE TABLE urun (id INTEGER PRIMARY KEY, ad TEXT, fiyat REAL);
CREATE TABLE ayar (anahtar TEXT, deger TEXT);
CREATE TABLE soru (id INTEGER PRIMARY KEY, metin TEXT);
CREATE TABLE log (mesaj TEXT);
"""


def ornek_db(dosya=":memory:", musteri=2000, siparis=20000, fts=False):
    """Örnekler için hep aynı içerikle dolan bir SQLite veritabanı."""
    r = random.Random(7)
    db = sqlite3.connect(dosya)
    db.executescript(_SEMA)
    db.executemany("INSERT INTO musteri VALUES (?, ?, ?, ?, ?, ?)", [
        (i, f"{r.choice(ADLAR)} {r.choice(SOYADLAR)}", r.choice(SEHIRLER), f"kisi{i}@ornek.com.tr",
         f"{r.randrange(1, 200)}. Sokak No: {r.randrange(1, 90)} " + "Mahalle " * 12,
         "Müşteri notu. " * 15) for i in range(1, musteri + 1)])
    db.executemany("INSERT INTO siparis VALUES (?, ?, ?, ?)", [
        (i, r.randrange(1, musteri + 1), r.randrange(10, 1000), f"2026-{r.randrange(1, 13):02d}-01")
        for i in range(1, siparis + 1)])
    db.executemany("INSERT INTO urun VALUES (?, ?, ?)", [(i, f"Ürün {i}", i * 2.5) for i in range(1, 5001)])
    db.executemany("INSERT INTO ayar VALUES (?, ?)", [(f"ayar{i}", str(i)) for i in range(2000)])
    db.executemany("INSERT INTO soru VALUES (?, ?)", [(i, f"Soru {i}: " + "metin " * 20) for i in range(1, 20001)])
    if fts:
        db.execute("CREATE VIRTUAL TABLE musteri_ara USING fts5(ad, tokenize='trigram')")
        db.execute("INSERT INTO musteri_ara (rowid, ad) SELECT id, ad FROM musteri")
    db.commit()
    return db


def yaz(yol, metin):
    with open(yol, "w", encoding="utf-8") as f:
        f.write(metin)
    return yol


YARDIMCILAR = {"ornek_db": ornek_db, "yaz": yaz, "ADLAR": ADLAR, "SOYADLAR": SOYADLAR,
               "SEHIRLER": SEHIRLER, "random": random, "os": os}


def fonksiyon_adi(kaynak):
    for d in ast.parse(kaynak).body:
        if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef)) and not d.name.startswith("_"):
            return d.name
    return None


# ---- çıktıları karşılaştırma ----

def normalle(x):
    """Farklı ama eşdeğer türleri (NumPy, pandas, Counter, Match) karşılaştırılabilir hâle getirir."""
    if x is None or isinstance(x, (bool, int, float, str, bytes)):
        return x
    if hasattr(x, "columns") and hasattr(x, "index"):                      # DataFrame
        return ("tablo", [str(c) for c in x.columns], normalle(x.index.tolist()),
                [normalle(x[c].tolist()) for c in x.columns])
    if hasattr(x, "index") and hasattr(x, "tolist") and hasattr(x, "dtype"):  # Series
        return ("seri", normalle(x.index.tolist()), normalle(x.tolist()))
    if hasattr(x, "tolist") and hasattr(x, "dtype"):                         # ndarray, NumPy skaleri
        return normalle(x.tolist())
    if isinstance(x, dict):
        return {normalle(k): normalle(v) for k, v in x.items()}
    if isinstance(x, (set, frozenset)):
        return frozenset(normalle(i) for i in x)
    if isinstance(x, (list, tuple)):
        return [normalle(i) for i in x]
    if hasattr(x, "group") and hasattr(x, "span"):                          # re.Match
        return ("eşleşme", x.group(), x.span())
    return x


def esit(a, b):
    if isinstance(a, float) or isinstance(b, float):
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            if math.isnan(a) and math.isnan(b):
                return True
            return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
        return False
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(esit(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(esit(a[k], b[k]) for k in a)
    return a == b


# ---- bir sürümü hazırlama ve çalıştırma ----

class _Surum:
    """Bir örneğin (kötü ya da iyi) kendi klasöründe çalışan hâli."""

    def __init__(self, kaynak, tanim):
        self.tanim = tanim
        self.klasor = tempfile.mkdtemp(prefix="yk-kanit-")
        self.onceki = os.getcwd()
        os.chdir(self.klasor)
        try:
            self.ns = {"__name__": "yk_ornek"}
            exec(tanim.get("ortam", ""), self.ns)
            exec(compile(kaynak, "<örnek>", "exec"), self.ns)
            self.fn = self.ns[tanim.get("fonk") or fonksiyon_adi(kaynak)]
            self.onbellekler = [v for v in self.ns.values() if callable(v) and hasattr(v, "cache_clear")]
        finally:
            os.chdir(self.onceki)

    def __enter__(self):
        os.chdir(self.klasor)
        return self

    def __exit__(self, *_):
        os.chdir(self.onceki)

    def hazirla(self):
        """Girdiyi kurar, (çağrı, yer) döndürür. Çağrı yalnızca fonksiyonu çalıştırır."""
        yer = dict(YARDIMCILAR, f=self.fn)
        exec(self.tanim.get("hazirla", "args = ()"), yer)
        cagir = self.tanim.get("cagir", "f(*args)")
        onbellekler = self.onbellekler
        if self.tanim.get("cikti"):
            exec(f"def __cagri():\n    with __yonlendir(__tampon):\n        return {cagir}", yer)
            yer["__tampon"] = io.StringIO()
            yer["__yonlendir"] = contextlib.redirect_stdout
        else:
            exec(f"def __cagri():\n    return {cagir}", yer)
        ic = yer["__cagri"]
        if onbellekler:
            def cagri():
                for o in onbellekler:
                    o.cache_clear()
                return ic()
        else:
            cagri = ic
        return cagri, yer

    def sonuc(self):
        cagri, yer = self.hazirla()
        yer["r"] = cagri()
        if self.tanim.get("cikti"):
            deger = yer["__tampon"].getvalue()
        elif "sonuc" in self.tanim:
            deger = eval(self.tanim["sonuc"], yer)
        else:
            deger = yer["r"]
        boyut = eval(self.tanim["boyut"], yer) if "boyut" in self.tanim else None
        return normalle(deger), boyut

    def bellek(self):
        cagri, _ = self.hazirla()
        tracemalloc.start()
        try:
            taban = tracemalloc.get_traced_memory()[0]
            cagri()
            return max(tracemalloc.get_traced_memory()[1] - taban, 0)
        finally:
            tracemalloc.stop()

    def kalibre(self):
        """Bir turun TUR_SURESI kadar sürmesi için çağrı sayısı. Tarayıcının saati kaba
        olabildiğinden (0,1 ms) tek çağrıya güvenilmez; timeit gibi katlanarak artırılır."""
        if self.tanim.get("taze"):
            t0 = time.perf_counter()
            cagri, _ = self.hazirla()                # taze ölçümde hazırlık da turun süresine girer
            cagri()
            bir = max(time.perf_counter() - t0, 1e-4)
            return max(1, min(int(TUR_SURESI / bir), 200))
        cagri, _ = self.hazirla()
        n = 1
        while True:
            t0 = time.perf_counter()
            for _ in range(n):
                cagri()
            gecen = time.perf_counter() - t0
            if gecen >= TUR_SURESI / 5 or n >= 1_000_000:
                break
            n *= 10 if gecen < TUR_SURESI / 100 else 2
        return max(1, min(int(n * TUR_SURESI / max(gecen, 1e-9)), 1_000_000))

    def tur(self, n):
        """n çağrının çağrı başına (süre, işlemci süresi) ortalaması."""
        if not self.tanim.get("taze"):
            cagri, _ = self.hazirla()
            c0, t0 = _islemci_saati(), time.perf_counter()
            for _ in range(n):
                cagri()
            return (time.perf_counter() - t0) / n, (_islemci_saati() - c0) / n
        sure = isl = 0.0
        for _ in range(n):
            cagri, _ = self.hazirla()          # her çağrı taze girdiyle; hazırlık ölçüme girmez
            c0, t0 = _islemci_saati(), time.perf_counter()
            cagri()
            sure += time.perf_counter() - t0
            isl += _islemci_saati() - c0
        return sure / n, isl / n

    def kapat(self):
        shutil.rmtree(self.klasor, ignore_errors=True)


def _islemci():
    if sys.platform == "darwin":
        try:
            import subprocess
            return subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True,
                                  text=True, timeout=2).stdout.strip() or None
        except (OSError, subprocess.SubprocessError):
            return None
    if sys.platform.startswith("linux"):
        try:
            for satir in _oku("/proc/cpuinfo").splitlines():
                if satir.startswith("model name"):
                    return satir.split(":", 1)[1].strip()
        except OSError:
            return None
    return platform.processor() or None


def ortam():
    tarayici = sys.platform == "emscripten"
    return {"python": platform.python_version(), "sistem": platform.system(), "makine": platform.machine(),
            "islemci": None if tarayici else _islemci(), "tarayici": tarayici}


def kanitla(kod, kotu, iyi, tanim, tur=TUR, bellek=True, ilerleme=None, olc=True):
    """Kötü ve iyi kaynağı karşılaştırıp ölçer; sonuç sözlüğü döndürür.
    olc=False ise yalnızca çıktıların aynı olup olmadığına bakılır."""
    sonuc = {"kod": kod, "ortam": ortam(), "not": tanim.get("not"), "not_en": tanim.get("not_en")}
    gerekli = tanim.get("python")
    if gerekli and sys.version_info < tuple(gerekli):
        return sonuc | {"atlandi": f"Python {'.'.join(map(str, gerekli))}+ gerekir"}
    surumler = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            a = _Surum(kotu, tanim)
            surumler.append(a)
            b = _Surum(iyi, tanim)
            surumler.append(b)
            with a:
                ca, boy_a = a.sonuc()
            with b:
                cb, boy_b = b.sonuc()
            if tanim.get("karsilastir", True) and not esit(ca, cb):
                return sonuc | {"esdeger": False, "hata": "İki sürüm farklı sonuç verdi."}
            sonuc["esdeger"] = True if tanim.get("karsilastir", True) else None
            if not olc:
                return sonuc
            with a:
                na = a.kalibre()
            with b:
                nb = b.kalibre()
            sa, sb = [], []
            for i in range(tur):
                with a:
                    sa.append(a.tur(na))
                with b:
                    sb.append(b.tur(nb))
                if ilerleme:
                    ilerleme((i + 1) / tur)
            olc_a = _ozet(sa)
            olc_b = _ozet(sb)
            if bellek:
                with a:
                    olc_a["bellek_b"] = a.bellek()
                with b:
                    olc_b["bellek_b"] = b.bellek()
            if boy_a is not None:
                olc_a["boyut_b"], olc_b["boyut_b"] = boy_a, boy_b
        except ModuleNotFoundError as e:
            return sonuc | {"atlandi": f"{e.name} kurulu değil"}
        finally:
            for s in surumler:
                s.kapat()
    olcut = tanim.get("olcut", "sure")
    sonuc |= {
        "kotu": olc_a, "iyi": olc_b, "olcut": olcut, "cagri": [na, nb],
        "kat": _oran(olc_a, olc_b, "islemci_s" if olcut == "islemci" else "sure_s"),
        "sure_kat": _oran(olc_a, olc_b, "sure_s"),
        "islemci_kat": _oran(olc_a, olc_b, "islemci_s"),
    }
    if bellek:
        sonuc["bellek_kat"] = _oran(olc_a, olc_b, "bellek_b")
    return sonuc


def _ozet(turlar):
    sure = statistics.median(t[0] for t in turlar)
    isl = statistics.median(t[1] for t in turlar)
    return {"sure_s": sure, "islemci_s": isl, "enerji_j": isl * config.CPU_WATTS_PER_CORE}


def _oran(a, b, alan):
    if not a.get(alan) or not b.get(alan):
        return None
    return a[alan] / b[alan]


def tanimlar(klasor):
    """ornekler/kurallar/olcum.py'deki OLCUM ve OLCULMEZ sözlüklerini yükler."""
    import runpy
    ns = runpy.run_path(os.path.join(klasor, "olcum.py"))
    return ns["OLCUM"], ns["OLCULMEZ"]


def _oku(yol):
    with open(yol, encoding="utf-8") as f:
        return f.read()


def hepsini_olc(klasor, secim=None, ilerleme=None):
    """Bütün kuralları (ya da seçilenleri) ölçer. Otomatik düzeltilen kurallarda
    motorun kendi çıktısı da aynı yöntemle sınanır."""
    from . import fixer
    olcum, olculmez = tanimlar(klasor)
    sonuclar = {}
    for kod in secim or sorted({*olcum, *olculmez}):
        if kod in olculmez:
            sonuclar[kod] = {"kod": kod, "olculmedi": olculmez[kod][0], "olculmedi_en": olculmez[kod][1]}
            if ilerleme:
                ilerleme(kod, sonuclar[kod])
            continue
        kotu = _oku(os.path.join(klasor, f"{kod}.py"))
        iyi = _oku(os.path.join(klasor, "iyi", f"{kod}.py"))
        r = kanitla(kod, kotu, iyi, olcum[kod])
        duzeltilmis, _, duzeltmeler = fixer.fix(kotu)
        if any(d.kural == kod for d in duzeltmeler) and r.get("esdeger") is not False:
            m = kanitla(kod, kotu, duzeltilmis, olcum[kod], tur=3, bellek=False)
            r["motor"] = {k: m.get(k) for k in ("esdeger", "kat", "sure_kat", "islemci_kat", "hata")}
        sonuclar[kod] = r
        if ilerleme:
            ilerleme(kod, r)
    return sonuclar
