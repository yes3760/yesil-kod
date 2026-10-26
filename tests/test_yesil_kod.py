"""Test paketi:  python -m unittest discover -s tests -v"""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from greencode import analyzer, fixer, proof, report, scenarios  # noqa: E402
from greencode.meter import EnergyMeter, to_co2_g, yearly_projection  # noqa: E402

ORNEK = (Path(__file__).resolve().parent.parent / "ornekler" / "israfli_ornek.py").read_text("utf-8")


def rules(code):
    return sorted(b["kural"] for b in analyzer.analyze(code)["bulgular"])


class AnalyzerTests(unittest.TestCase):
    def test_ornek_dosyadaki_tum_kurallar(self):
        self.assertEqual(sorted(set(rules(ORNEK))), [f"YK00{i}" for i in range(1, 10)])

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


class ReportTests(unittest.TestCase):
    def test_rapor_ornek_dosyayi_bulur(self):
        p = Path(__file__).resolve().parent.parent / "ornekler"
        rep = report.scan([p])
        self.assertGreaterEqual(rep["toplam"]["yüksek"], 3)
        self.assertIn("Yeşil Kod raporu", report.to_markdown(rep))


if __name__ == "__main__":
    unittest.main()
