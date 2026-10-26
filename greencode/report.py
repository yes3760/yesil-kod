"""CI raporu: bir dizindeki tüm Python dosyalarını tarar, bulguları ve
otomatik düzeltilebilecekleri raporlar.

  python -m greencode rapor src/ --bicim md   > yesil-kod.md
  python -m greencode rapor src/ --bicim json > yesil-kod.json
  python -m greencode rapor src/ --esik 0      # yüksek önemli bulgu varsa çıkış kodu 1

GitHub Action örneği: ornekler/github-action.yml
"""
from __future__ import annotations

import html
import json
import os
from pathlib import Path

from . import analyzer, fixer

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "build", "dist", ".tox"}


def iter_py(paths):
    for p in paths:
        p = Path(p)
        if p.is_file() and p.suffix == ".py":
            yield p
        elif p.is_dir():
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for f in sorted(files):
                    if f.endswith(".py"):
                        yield Path(root) / f


def scan(paths):
    files = []
    for p in iter_py(paths):
        try:
            code = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        r = analyzer.analyze(code)
        if r["hata"]:
            files.append({"dosya": str(p), "hata": r["hata"], "bulgular": [], "duzeltilebilir": 0})
            continue
        try:
            _, _, fixes = fixer.fix(code)
            n_fix = len(fixes)
        except Exception:
            n_fix = 0
        files.append({"dosya": str(p), "hata": None, "bulgular": r["bulgular"], "duzeltilebilir": n_fix})
    tally = {"yüksek": 0, "orta": 0, "bilgi": 0}
    for f in files:
        for b in f["bulgular"]:
            tally[b["onem"]] += 1
    return {"dosya_sayisi": len(files), "toplam": tally,
            "duzeltilebilir": sum(f["duzeltilebilir"] for f in files),
            "dosyalar": [f for f in files if f["bulgular"] or f["hata"]]}


def to_markdown(rep):
    t = rep["toplam"]
    lines = ["## Yeşil Kod raporu", "",
             f"{rep['dosya_sayisi']} dosya tarandı: **{t['yüksek']} yüksek**, {t['orta']} orta, "
             f"{t['bilgi']} bilgi düzeyinde bulgu. Otomatik düzeltilebilir: **{rep['duzeltilebilir']}**.", ""]
    if not rep["dosyalar"]:
        lines.append("Bilinen bir enerji israfı kalıbı bulunamadı.")
        return "\n".join(lines)
    lines += ["| Dosya | Satır | Kural | Önem | Bulgu |", "| --- | --- | --- | --- | --- |"]
    for f in rep["dosyalar"]:
        if f["hata"]:
            lines.append(f"| `{f['dosya']}` | | | | {f['hata']} |")
        for b in f["bulgular"]:
            lines.append(f"| `{f['dosya']}` | {b['satir']} | {b['kural']} | {b['onem']} | {b['baslik']} |")
    lines += ["", "Düzeltmeyi görmek için: `python -m greencode duzelt <dosya>`"]
    return "\n".join(lines)


def to_html(rep):
    rows = "".join(
        f"<tr><td><code>{html.escape(f['dosya'])}</code></td><td>{b['satir']}</td><td>{b['kural']}</td>"
        f"<td>{b['onem']}</td><td>{html.escape(b['baslik'])}<br><small>{html.escape(b['oneri'])}</small></td></tr>"
        for f in rep["dosyalar"] for b in f["bulgular"])
    t = rep["toplam"]
    return f"""<!doctype html><html lang="tr"><meta charset="utf-8"><title>Yeşil Kod raporu</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:1000px;margin:40px auto;padding:0 20px;color:#15201b;background:#e8ebe7}}
table{{border-collapse:collapse;width:100%;background:#f4f6f3}}td,th{{border:1px solid #b9c2bc;padding:8px;text-align:left;vertical-align:top}}
small{{color:#4a5a51}}</style>
<h1>Yeşil Kod raporu</h1><p>{rep['dosya_sayisi']} dosya · {t['yüksek']} yüksek · {t['orta']} orta · {t['bilgi']} bilgi ·
otomatik düzeltilebilir: {rep['duzeltilebilir']}</p>
<table><tr><th>Dosya</th><th>Satır</th><th>Kural</th><th>Önem</th><th>Bulgu ve öneri</th></tr>{rows}</table></html>"""


def to_json(rep):
    return json.dumps(rep, ensure_ascii=False, indent=2)
