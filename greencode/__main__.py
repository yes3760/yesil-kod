"""Komut satırı.

  python -m greencode                          canlı paneli başlatır
  python -m greencode senaryolar               4 senaryoyu otomatik düzeltir, doğrular, ölçer
  python -m greencode analiz dosya.py          israf kalıplarını listeler
  python -m greencode duzelt dosya.py          düzeltilmiş kodun farkını gösterir
        --yaz                                  dosya.yesil.py olarak kaydeder
        --kanitla FONKSIYON                    parametresiz FONKSIYON'u iki sürümde
                                               çalıştırıp sonucu karşılaştırır ve ölçer
  python -m greencode olc dosya.py             betiği çalıştırıp enerjisini ölçer
  python -m greencode rapor DİZİN [--bicim md|html|json] [--esik N]
"""
import argparse
import runpy
import sys
from pathlib import Path

from . import analyzer, config, fixer, proof, report, scenarios
from .meter import EnergyMeter

GREEN, AMBER, DIM, BOLD, END = "\033[32m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"
if not sys.stdout.isatty():
    GREEN = AMBER = DIM = BOLD = END = ""


def fmt_j(j):
    if j >= 1:
        return f"{j:.2f} J"
    if j >= 1e-3:
        return f"{j*1e3:.2f} mJ"
    return f"{j*1e6:.1f} µJ"


def cmd_senaryolar(_):
    m = EnergyMeter()
    data = scenarios.build_data()
    print(f"\nÖlçüm: {m.info()['mode_label']} · {config.REPEATS} tekrar · "
          f"{config.CARBON_INTENSITY_G_PER_KWH:g} gCO2e/kWh\n")
    print(f"{'Senaryo':22} {'Düzeltme':10} {'Eşdeğer':8} {'Özgün':>11} {'Düzeltilmiş':>12} {'Fark':>9}  Yıllık*")
    for s in scenarios.SCENARIOS:
        r = proof.prove(s["kod"], s["giris"], data, m)
        kurallar = ",".join(sorted({f["kural"] for f in r["duzeltmeler"]})) or "-"
        if not r["esdeger"]:
            print(f"{s['baslik']:22} {kurallar:10} {'HAYIR':8} {r['hata']}")
            continue
        a, b = r["ozgun"], r["duzeltilmis"]
        tas = a["yillik"]["co2_kg"] - b["yillik"]["co2_kg"]
        q = r["sorgu_sayisi"]
        extra = f"   sorgu {q['ozgun']} -> {q['duzeltilmis']}" if q else ""
        print(f"{s['baslik']:22} {kurallar:10} {'evet':8} {fmt_j(a['energy_j']):>11} "
              f"{fmt_j(b['energy_j']):>12} {r['kat']:>8.1f}x  {tas:.1f} kg CO2e{extra}")
    print(f"\n* Günde {config.DAILY_CALLS:,} istekte 1 yıllık tasarruf.\n".replace(",", "."))


def cmd_analiz(a):
    r = analyzer.analyze(Path(a.dosya).read_text(encoding="utf-8"))
    if r["hata"]:
        sys.exit(r["hata"])
    if not r["bulgular"]:
        print("Bilinen bir israf kalıbı bulunamadı.")
    for b in r["bulgular"]:
        col = AMBER if b["onem"] == "yüksek" else ""
        print(f"{a.dosya}:{b['satir']}  {col}{b['kural']} {b['onem']}{END}  {b['baslik']}"
              + (f"  {DIM}({b['detay']}){END}" if b["detay"] else ""))
        print(f"    {DIM}{b['oneri']}{END}")


def cmd_duzelt(a):
    src = Path(a.dosya)
    code = src.read_text(encoding="utf-8")
    new, orig, fixes = fixer.fix(code)
    if not fixes:
        print("Otomatik düzeltilebilecek bir kalıp bulunamadı.")
        return
    for line in fixer.unified_diff(orig, new, src.name).splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            print(GREEN + line + END)
        elif line.startswith("-") and not line.startswith("---"):
            print(AMBER + line + END)
        else:
            print(DIM + line + END)
    print()
    for f in fixes:
        print(f"  {BOLD}{f.kural}{END} satır {f.satir}: {f.aciklama}")
    if a.yaz:
        out = src.with_suffix(".yesil.py")
        out.write_text(new + "\n", encoding="utf-8")
        not_ = "yorumlar ve biçim korundu" if fixer.fix.bicim_korundu else "kod yeniden biçimlendirildi"
        print(f"\nKaydedildi: {out} ({not_})")
    if a.kanitla:
        m = EnergyMeter()
        data = {"__name__": "yesil_kanit"}
        r = proof.prove(code, a.kanitla, data, m)
        if not r["esdeger"]:
            sys.exit(f"\n{AMBER}{r['hata']}{END}")
        print(f"\n{GREEN}Aynı sonuç doğrulandı.{END} {m.info()['mode_label']}")
        print(f"  Özgün       : {fmt_j(r['ozgun']['energy_j'])}")
        print(f"  Düzeltilmiş : {fmt_j(r['duzeltilmis']['energy_j'])}  ({r['kat']:.1f} kat daha az)")


def cmd_olc(a):
    m = EnergyMeter()
    sys.argv = [a.dosya] + a.args
    r = m.measure(lambda: runpy.run_path(a.dosya, run_name="__main__"), repeats=a.tekrar, min_seconds=0)
    print(f"\n{a.dosya}  ({m.info()['mode_label']}, {r.repeats} tekrar)")
    print(f"  Süre   : {r.wall_s:.3f} s")
    print(f"  Enerji : {fmt_j(r.energy_j)}  (± {fmt_j(r.energy_j_std)})")
    print(f"  Karbon : {r.co2_g * 1000:.3f} mg CO2e")


def cmd_rapor(a):
    rep = report.scan(a.yollar)
    out = {"md": report.to_markdown, "html": report.to_html, "json": report.to_json}[a.bicim](rep)
    print(out)
    if a.esik is not None and rep["toplam"]["yüksek"] > a.esik:
        sys.exit(1)


def main():
    p = argparse.ArgumentParser(prog="greencode", description="Yeşil Kod")
    sub = p.add_subparsers(dest="komut")
    sub.add_parser("sunucu")
    sub.add_parser("senaryolar")
    pa = sub.add_parser("analiz"); pa.add_argument("dosya")
    pd = sub.add_parser("duzelt"); pd.add_argument("dosya")
    pd.add_argument("--yaz", action="store_true"); pd.add_argument("--kanitla", metavar="FONKSIYON")
    po = sub.add_parser("olc"); po.add_argument("dosya"); po.add_argument("args", nargs="*")
    po.add_argument("--tekrar", type=int, default=3)
    pr = sub.add_parser("rapor"); pr.add_argument("yollar", nargs="+")
    pr.add_argument("--bicim", choices=["md", "html", "json"], default="md")
    pr.add_argument("--esik", type=int, default=None)
    a = p.parse_args()
    if a.komut in (None, "sunucu"):
        from .server import serve
        serve()
    else:
        {"senaryolar": cmd_senaryolar, "analiz": cmd_analiz, "duzelt": cmd_duzelt,
         "olc": cmd_olc, "rapor": cmd_rapor}[a.komut](a)


if __name__ == "__main__":
    main()
