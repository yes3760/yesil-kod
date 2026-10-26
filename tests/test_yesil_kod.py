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
        self.assertEqual(sorted(set(rules(ORNEK))), ["YK001", "YK002", "YK003", "YK004", "YK005", "YK006"])

    def test_dongu_ifadesi_bir_kez_calisir_isaretlenmez(self):
        code = "def f(db):\n    for r in db.execute('SELECT 1'):\n        print(r)\n"
        self.assertNotIn("YK001", rules(code))

    def test_onbellekli_ozyineleme_isaretlenmez(self):
        code = "import functools\n@functools.lru_cache\ndef f(n):\n    return n if n<2 else f(n-1)+f(n-2)\n"
        self.assertNotIn("YK004", rules(code))

    def test_donguye_bagli_cagri_tasinmaz(self):
        code = "import json\ndef f(xs):\n    for x in xs:\n        json.loads(x)\n"
        self.assertNotIn("YK003", rules(code))

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
