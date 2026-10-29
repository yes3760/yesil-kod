"""Test paketi:  python -m unittest discover -s tests -v"""
import ast
import plistlib
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from greencode import analyzer, fixer, kural_ayrinti, kural_kanit, proof, report, scenarios  # noqa: E402
from greencode.meter import EnergyMeter, _PowerMetrics, to_co2_g, yearly_projection  # noqa: E402

ORNEK = (Path(__file__).resolve().parent.parent / "ornekler" / "israfli_ornek.py").read_text("utf-8")
KURAL_KLASORU = Path(__file__).resolve().parent.parent / "ornekler" / "kurallar"


def rules(code):
    return sorted(b["kural"] for b in analyzer.analyze(code)["bulgular"])


class AnalyzerTests(unittest.TestCase):
    def test_ornek_dosyadaki_tum_kurallar(self):
        self.assertTrue({f"YK00{i}" for i in range(1, 10)} <= set(rules(ORNEK)))

    def test_dongu_ifadesi_bir_kez_calisir_isaretlenmez(self):
        code = "def f(db):\n    for r in db.execute('SELECT 1'):\n        print(r)\n"
        self.assertNotIn("YK001", rules(code))

    def test_onbellekli_ozyineleme_isaretlenmez(self):
        code = "import functools\n@functools.lru_cache\ndef f(n):\n    return n if n<2 else f(n-1)+f(n-2)\n"
        self.assertNotIn("YK004", rules(code))

    def test_donguye_bagli_cagri_tasinmaz(self):
        code = "import json\ndef f(xs):\n    for x in xs:\n        json.loads(x)\n"
        self.assertNotIn("YK003", rules(code))

    def test_pandas_satir_satir(self):
        self.assertIn("YK007", rules("def f(df):\n    return [r.a for _, r in df.iterrows()]\n"))
        self.assertIn("YK007", rules("def f(df):\n    return df.apply(g, axis=1)\n"))
        self.assertNotIn("YK007", rules("def f(df):\n    return df.apply(g)\n"))

    def test_oturumsuz_http(self):
        self.assertIn("YK008", rules("import requests\ndef f(us):\n    for u in us:\n        requests.get(u)\n"))
        self.assertNotIn("YK008", rules("import requests\ndef f(s, us):\n    for u in us:\n        s.get(u)\n"))

    def test_liste_basindan_cikarma(self):
        self.assertIn("YK009", rules("def f(q):\n    while q:\n        q.pop(0)\n"))
        self.assertNotIn("YK009", rules("def f(q):\n    while q:\n        q.pop()\n"))

    def test_her_kuralin_ornegi_kendi_kuralini_tetikler(self):
        klasor = Path(__file__).resolve().parent.parent / "ornekler" / "kurallar"
        for kod in analyzer.RULES:
            with self.subTest(kod):
                self.assertIn(kod, rules((klasor / f"{kod}.py").read_text("utf-8")))

    def test_yanlis_alarm_vermez(self):
        temiz = {
            "YK028": "def f(satirlar):\n    for s in satirlar:\n        s.split()\n",
            "YK012": "def f(yollar):\n    for y in yollar:\n        open(y).read()\n",
            "YK010": "def f(xs):\n    toplam = 0\n    for x in xs:\n        toplam += x\n    return toplam\n",
            "YK013": "def f(xs, metin):\n    for x in xs:\n        metin.index(x)\n",
            "YK015": "def f(x):\n    while x:\n        x = adim(x)\n",
            "YK027": "def f(a):\n    for i in range(len(a)):\n        a[i] = a[i] * 2\n",
            "YK029": "def f(d):\n    for k in list(d):\n        del d[k]\n",
            "YK017": "def f(xs):\n    s = []\n    for x in xs:\n        s += [x]\n    return s\n",
            "YK011": "def f(xs):\n    return sorted(xs)[1]\n",
            "YK004": "def gez(d):\n    if d:\n        gez(d.sol)\n        gez(d.sag)\n",
            "YK036": "def f(db, i):\n    return db.execute('SELECT ad FROM m WHERE id = ?', (i,)).fetchone()\n",
            "YK082": "def f(m, i, j, v):\n    m[i][j] = v\n",
            "YK034": "def f(resimler):\n    for r in resimler:\n        r.save('a.png')\n",
            "YK062": "def f(x):\n    return list(set(x))\n",
            "YK047": "def f(xs):\n    out = []\n    for x in xs:\n        p = []\n        p.append(x)\n        out.append(','.join(p))\n    return out\n",
            "YK090": "def f(xs, birim):\n    for x in xs:\n        x.to(birim)\n",
            "YK100": "def f(x):\n    print(x)\n",
            "YK015": "def f(dosya):\n    while dosya.read(8192):\n        pass\n",
            "YK012": "def f(yol):\n    while True:\n        try:\n            return open(yol)\n        except OSError:\n            pass\n",
            "YK004 ": "def hanoi(n, a, b, c):\n    if n:\n        hanoi(n - 1, a, c, b)\n        print(a, c)\n        hanoi(n - 1, b, a, c)\n",
            "YK056": "def f(xs):\n    for i in range(len(xs)):\n        print(i)\n",
        }
        for kural, kod in temiz.items():
            with self.subTest(kural):
                self.assertNotIn(kural.strip(), rules(kod))

    def test_bekleme_ve_ozyineleme_yakalanir(self):
        self.assertIn("YK015", rules("def f(t):\n    while not t.is_set():\n        pass\n"))
        self.assertIn("YK004", rules("def f(n):\n    return n if n < 2 else f(n - 1) + f(n - 2)\n"))

    def test_kurgu_kaynagi_bir_kez_calisir(self):
        # Liste kurgusunun ilk kaynağı döngü değildir: dosyayı bir kez açar
        self.assertNotIn("YK012", rules("def f(p):\n    return [s for s in open(p)]\n"))

    def test_her_kuralin_bir_kategorisi_var(self):
        self.assertEqual(sorted(analyzer.CATEGORY_OF), sorted(analyzer.RULES))

    def test_sozdizimi_hatasi(self):
        self.assertIsNotNone(analyzer.analyze("def (:")["hata"])


class FixerTests(unittest.TestCase):
    def test_her_senaryo_duzeltilir_ve_ayni_sonucu_verir(self):
        data = scenarios.build_data()
        for s in scenarios.SCENARIOS:
            with self.subTest(s["id"]):
                run_a, run_b, new, _, fixes = proof.prepare(s["kod"], s["giris"], data)
                self.assertTrue(fixes, "düzeltme bulunamadı")
                ast.parse(new)
                self.assertTrue(proof.verify(run_a, run_b)[0])

    def test_liste_donguyde_degisirse_kumeye_cevrilmez(self):
        code = ("def f(xs):\n    seen = []\n    for x in xs:\n        if x not in seen:\n"
                "            seen.append(x)\n    return seen\n")
        _, _, fixes = fixer.fix(code)
        self.assertFalse([f for f in fixes if f.kural == "YK002"])

    def test_n_arti_1_sorgu_sayisini_dusurur(self):
        data = scenarios.build_data()
        s = scenarios.get("n-arti-1")
        run_a, run_b, *_ = proof.prepare(s["kod"], s["giris"], data)
        ns_a, ns_b = proof.prepare.last_ns
        run_a(); run_b()
        self.assertGreater(ns_a["DB"].count, 4000)
        self.assertLess(ns_b["DB"].count, 10)

    def test_ornek_dosya_gecerli_python_uretir(self):
        new, _, fixes = fixer.fix(ORNEK)
        ast.parse(new)
        self.assertGreaterEqual(len(fixes), 4)

    def test_yorumlar_ve_bicim_korunur(self):
        code = ("import json\n\n\n# Fiyat hesabı\ndef f(xs, ayar):\n    out = []  # sonuç\n"
                "    for x in xs:  # her eleman\n        cfg = json.loads(ayar)  # israf\n"
                "        out.append(x * cfg[\"k\"])\n    return out\n")
        new, orig, fixes = fixer.fix(code)
        self.assertTrue(fixer.fix.bicim_korundu)
        self.assertEqual(orig, code)
        for parca in ("# Fiyat hesabı", "# sonuç", "# her eleman", "# israf", 'cfg["k"]'):
            self.assertIn(parca, new)
        degisen = [s for s in fixer.unified_diff(orig, new).splitlines()
                   if s[:1] in "+-" and not s.startswith(("+++", "---"))]
        self.assertEqual(len(degisen), 2)                     # yalnızca taşınan satır

    def test_bicim_korunan_sonuc_tam_yeniden_yazimla_ayni(self):
        for code in [ORNEK] + [s["kod"] for s in scenarios.SCENARIOS]:
            with self.subTest(code[:30]):
                new, _, fixes = fixer.fix(code)
                self.assertTrue(fixer.fix.bicim_korundu)
                f = fixer.Fixer(code)
                self.assertEqual(ast.dump(ast.parse(new)), ast.dump(ast.parse(f.run())))

    def test_elif_dali_elif_kalir(self):
        code = ("def f(xs, k, kayit):\n    if k == 1:\n        return 0\n    elif k == 2:\n"
                "        kayitlar = list(kayit)\n        return [x for x in xs if x in kayitlar]\n")
        new, _, fixes = fixer.fix(code)
        self.assertTrue(fixer.fix.bicim_korundu)
        self.assertIn("    elif k == 2:", new)
        self.assertIn("kayitlar_kume = set(kayitlar)", new)

    def test_siralama_yerine_min_max_ayni_sonucu_verir(self):
        code = ("def f(xs):\n    return (sorted(xs)[0], sorted(xs, key=lambda x: -x)[0],\n"
                "            sorted(xs, reverse=True)[0], sorted(xs)[-1])\n")
        new, _, fixes = fixer.fix(code)
        self.assertEqual(sum(1 for f in fixes if f.kural == "YK011"), 3)    # [-1] bilerek düzeltilmez
        ns_a, ns_b = {}, {}
        exec(code, ns_a); exec(new, ns_b)
        for xs in ([3, 1, 2], [5, 5, 1, 9, 9], [2.0, 2, 1, 2]):     # eşit ama farklı nesneler: kararlılık
            self.assertEqual([repr(v) for v in ns_a["f"](xs)], [repr(v) for v in ns_b["f"](xs)])

    def test_list_range_kopyasi_kaldirilir(self):
        new, _, fixes = fixer.fix("def f(n):\n    return [i * i for i in list(range(n))]\n")
        self.assertIn("for i in range(n)", new)
        self.assertEqual([f.kural for f in fixes], ["YK029"])

    def test_dongude_degistirilen_sonuc_disari_tasinmaz(self):
        code = ("import json\ndef f(t, xs):\n    out = []\n    for x in xs:\n        ayar = json.loads(t)\n"
                "        ayar['n'] = ayar.get('n', 0) + x\n        out.append(ayar['n'])\n    return out\n")
        new, _, fixes = fixer.fix(code)
        self.assertFalse([f for f in fixes if f.kural == "YK003"])
        ns = {}
        exec(new, ns)
        self.assertEqual(ns["f"]('{"n": 1}', [1, 2]), [2, 3])

    def test_ayni_satirda_iki_ifade_guvenli_yola_doner(self):
        code = "def f(xs, k):\n    ks = list(k); return [x for x in xs if x in ks]\n"
        new, _, fixes = fixer.fix(code)
        ast.parse(new)
        self.assertIn("set(ks)", new)


class MeterTests(unittest.TestCase):
    def test_karbon_donusumu(self):
        # 3,6 MJ = 1 kWh -> yoğunluk kadar gram
        from greencode import config
        self.assertAlmostEqual(to_co2_g(3_600_000), config.CARBON_INTENSITY_G_PER_KWH)

    def test_yillik_projeksiyon_olceklenir(self):
        a, b = yearly_projection(1.0), yearly_projection(2.0)
        self.assertAlmostEqual(b["kwh"], 2 * a["kwh"])

    def test_olcum_pozitif(self):
        r = EnergyMeter().measure(lambda: sum(range(20000)), repeats=2, min_seconds=0.05)
        self.assertGreater(r.energy_j, 0)


class PowerMetricsTests(unittest.TestCase):
    """macOS donanım ölçümü: ayrıştırma ve pencere hesabı (sudo gerektirmez)."""

    def test_apple_silicon_ornegi(self):
        ornek = plistlib.dumps({"elapsed_ns": 100_000_000, "processor": {"cpu_energy": 250, "cpu_power": 2500.0}})
        dt, e = _PowerMetrics.parse(ornek + b"\n")
        self.assertAlmostEqual(dt, 0.1)
        self.assertAlmostEqual(e, 0.25)                    # 250 mJ

    def test_akistaki_ornekler_ayirici_beklenmeden_okunur(self):
        # Gerçek akış: <plist>…</plist>\n\0<plist>…; son örneğin ayırıcısı henüz gelmemiş
        ornek = lambda mj: plistlib.dumps({"elapsed_ns": 100_000_000, "is_delta": True,
                                           "processor": {"cpu_energy": mj, "cpu_power": mj * 10.0, "clusters": []}})
        akis = ornek(200) + b"\0" + ornek(300)
        pm = _PowerMetrics(start=False)

        class Akis:
            def __init__(self, parcalar): self.parcalar = list(parcalar)
            def read1(self, n): return self.parcalar.pop(0) if self.parcalar else b""

        pm._proc = type("P", (), {"stdout": Akis([akis[:50], akis[50:]])})()
        pm._read()
        self.assertEqual([round(e, 3) for _, _, e in pm.samples], [0.2, 0.3])

    def test_yalnizca_guc_varsa_sureyle_carpilir(self):
        ornek = plistlib.dumps({"elapsed_ns": 200_000_000, "processor": {"cpu_power": 1500.0}})
        self.assertAlmostEqual(_PowerMetrics.parse(ornek)[1], 0.3)

    def test_bozuk_ornek_yok_sayilir(self):
        self.assertIsNone(_PowerMetrics.parse(b""))
        self.assertIsNone(_PowerMetrics.parse(b"<?xml version"))
        self.assertIsNone(_PowerMetrics.parse(plistlib.dumps({"elapsed_ns": 0, "processor": {}})))

    def test_pencere_enerjisi_ortusen_orneklerden(self):
        pm = _PowerMetrics(start=False)
        now = time.perf_counter()
        for k in range(10):                                 # 2 W sabit, 100 ms örnekler
            pm.samples.append((now - 1 + 0.1 * (k + 1), 0.1, 0.2))
        self.assertAlmostEqual(pm.energy_between(now - 0.75, now - 0.25), 1.0, places=6)
        self.assertAlmostEqual(pm.energy_between(now - 0.05, now), 0.1, places=6)


class ReportTests(unittest.TestCase):
    def test_rapor_ornek_dosyayi_bulur(self):
        p = Path(__file__).resolve().parent.parent / "ornekler"
        rep = report.scan([p])
        self.assertGreaterEqual(rep["toplam"]["yüksek"], 3)
        self.assertIn("Yeşil Kod raporu", report.to_markdown(rep))


class KuralKanitTests(unittest.TestCase):
    """Her kuralın iyi örneği, ayrıntısı ve ölçüm tanımı; kötü ve iyi sürümün aynı sonucu vermesi."""

    @classmethod
    def setUpClass(cls):
        cls.olcum, cls.olculmez = kural_kanit.tanimlar(str(KURAL_KLASORU))

    def test_her_kuralin_iyi_ornegi_temiz(self):
        for kod in analyzer.RULES:
            with self.subTest(kod):
                self.assertEqual(rules((KURAL_KLASORU / "iyi" / f"{kod}.py").read_text("utf-8")), [])

    def test_ayrinti_ve_olcum_tanimi_her_kurali_kapsar(self):
        self.assertEqual(set(kural_ayrinti.AYRINTI), set(analyzer.RULES))
        self.assertEqual(set(self.olcum) | set(self.olculmez), set(analyzer.RULES))
        self.assertFalse(set(self.olcum) & set(self.olculmez))
        for kod, (neden, why, istisna, exception, karmasiklik, url) in kural_ayrinti.AYRINTI.items():
            with self.subTest(kod):
                self.assertTrue(all((neden, why, istisna, exception, karmasiklik)))
                self.assertTrue(url.startswith("https://"))
                self.assertNotRegex(kural_ayrinti.karmasiklik_en(kod), "[çğışöüÇĞİŞÖÜ]")
        for kod, tanim in self.olcum.items():
            with self.subTest(kod):
                self.assertEqual(bool(tanim.get("not")), bool(tanim.get("not_en")))

    def test_kotu_ve_iyi_ornek_ayni_sonucu_verir(self):
        import sqlite3
        for kod, tanim in sorted(self.olcum.items()):
            with self.subTest(kod):
                kotu = (KURAL_KLASORU / f"{kod}.py").read_text("utf-8")
                iyi = (KURAL_KLASORU / "iyi" / f"{kod}.py").read_text("utf-8")
                try:
                    r = kural_kanit.kanitla(kod, kotu, iyi, tanim, olc=False)
                except sqlite3.OperationalError as e:          # eski SQLite: FTS5 trigram yok
                    self.skipTest(str(e))
                if "atlandi" in r:
                    continue                                     # numpy, pandas ... kurulu değil
                self.assertIsNot(r["esdeger"], False, r.get("hata"))

    def test_motorun_duzeltmesi_de_ayni_sonucu_verir(self):
        for kod in ("YK002", "YK003", "YK004", "YK011", "YK029", "YK062", "YK064", "YK065", "YK066", "YK113"):
            with self.subTest(kod):
                kotu = (KURAL_KLASORU / f"{kod}.py").read_text("utf-8")
                yeni, _, duzeltmeler = fixer.fix(kotu)
                self.assertIn(kod, {d.kural for d in duzeltmeler})
                r = kural_kanit.kanitla(kod, kotu, yeni, self.olcum[kod], olc=False)
                self.assertTrue(r["esdeger"])

    def test_kayitli_olcumler_tam_ve_esdeger(self):
        import json
        kayit = json.loads((KURAL_KLASORU / "olcumler.json").read_text("utf-8"))["sonuclar"]
        self.assertEqual(set(kayit), set(analyzer.RULES))
        for kod, r in kayit.items():
            with self.subTest(kod):
                if kod in self.olculmez:
                    self.assertIn("olculmedi", r)
                else:
                    self.assertIsNot(r["esdeger"], False)
                    self.assertGreater(r["kat"], 0)

    def test_normalle_ve_esit(self):
        from collections import Counter
        n, e = kural_kanit.normalle, kural_kanit.esit
        self.assertTrue(e(n(Counter("aab")), n({"a": 2, "b": 1})))
        self.assertTrue(e(n((1, [2, 3])), n([1, (2, 3)])))
        self.assertTrue(e(n(3.0000000000000004), n(3.0)))
        self.assertFalse(e(n(3.1), n(3.0)))
        self.assertTrue(e(n({1, 2}), n({2, 1})))
        self.assertFalse(e(n([1, 2]), n([2, 1])))

    def test_ardisik_startswith(self):
        self.assertIn("YK071", rules("def f(s):\n    return s.startswith('a') or s.startswith('b')\n"))
        self.assertNotIn("YK071", rules("def f(s, t):\n    return s.startswith('a') or t.startswith('b')\n"))
        self.assertNotIn("YK071", rules("def f(s):\n    return s.startswith('a') or s.endswith('b')\n"))


if __name__ == "__main__":
    unittest.main()
