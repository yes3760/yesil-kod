"""Stant malzemelerini üretir: proje sitesi, QR kodları, PDF'ler ve film.

    python3 stant/hazirla.py            hepsini üretir
    python3 stant/hazirla.py site       docs/ klasörünü (GitHub Pages) günceller
    python3 stant/hazirla.py qr         QR kodlarını üretir          (gerekir: pip install segno)
    python3 stant/hazirla.py pdf        PDF'leri üretir               (gerekir: Google Chrome; önizleme için pymupdf)
    python3 stant/hazirla.py film       filmi QR kapanışıyla yeniden üretir (gerekir: ffmpeg)

Ekip adı, adresler ve etkinlik bilgisi stant/ayarlar.json dosyasındadır.
O dosyayı değiştirip bu betiği yeniden çalıştırmanız yeterli.
"""
from __future__ import annotations

import functools
import html
import http.server
import json
import os
import platform
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

STANT = Path(__file__).resolve().parent
ROOT = STANT.parent
DOCS = ROOT / "docs"
KAYNAK = STANT / "kaynak"
QR_DIR = STANT / "qr"
PDF_DIR = STANT / "pdf"
ONIZLEME = STANT / "onizleme"
FILM_DIR = STANT / "film"
FILM_SRC = Path(os.getenv("YK_FILM", str(Path.home() / "Downloads" / "yesil-kod-film.mp4")))

AYAR = json.loads((STANT / "ayarlar.json").read_text("utf-8"))

# Basılacak belgeler: (kaynak html, çıktı pdf)
BELGELER = [
    ("poster.html", "01-poster-A0.pdf"),
    ("brosur.html", "02-brosur-A5-TR.pdf"),
    ("brosur-en.html", "03-brochure-A5-EN.pdf"),
    ("masa-karti.html", "04-masa-karti-A4.pdf"),
    ("proje-ozeti.html", "05-proje-ozeti-A4.pdf"),
    ("sunum.html", "06-ekran-sunumu-16x9.pdf"),
    ("stant-rehberi.html", "07-stant-rehberi-A4.pdf"),
    ("video-brif.html", "08-video-brifi-A4.pdf"),
]


# ------------------------------------------------------------------ yardımcılar
def degiskenler():
    ekip = AYAR["ekip"]
    d = {k: v for k, v in AYAR.items() if isinstance(v, str)}
    d["ekip"] = " · ".join(ekip)
    d["ekip_en"] = d["ekip"]
    d["danisman_satiri"] = f"Danışman: {AYAR['danisman']}" if AYAR.get("danisman") else ""
    d["advisor_line"] = f"Advisor: {AYAR['danisman']}" if AYAR.get("danisman") else ""
    d["dene_url"] = AYAR["site_url"] + "#dene"
    return d


def doldur(metin: str) -> str:
    for k, v in degiskenler().items():
        metin = metin.replace("{{" + k + "}}", html.escape(v))
    return metin


def chrome_yolu():
    adaylar = {
        "Darwin": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                   "/Applications/Chromium.app/Contents/MacOS/Chromium",
                   "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"],
        "Windows": [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"],
    }.get(platform.system(), [])
    adaylar += [shutil.which(n) for n in ("google-chrome", "chromium", "chromium-browser", "chrome")]
    for a in adaylar:
        if a and Path(a).exists():
            return a
    sys.exit("Google Chrome bulunamadı. PDF üretimi için Chrome gerekir.")


class _Sessiz(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def sunucu():
    """Proje kökünü yerel olarak sunar (Chrome yazı tiplerini file:// üzerinden yüklemez)."""
    h = functools.partial(_Sessiz, directory=str(ROOT))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def chrome(args, profil):
    cmd = [chrome_yolu(), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
           "--no-default-browser-check", f"--user-data-dir={profil}", "--virtual-time-budget=8000"] + args
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def render_html(ad):
    """kaynak/ad dosyasını ayarlarla doldurup kaynak/_render/ altına yazar; sunucu yolunu döndürür."""
    hedef = KAYNAK / "_render" / ad
    hedef.parent.mkdir(exist_ok=True)
    hedef.write_text(doldur((KAYNAK / ad).read_text("utf-8")), "utf-8")
    return "/" + hedef.relative_to(ROOT).as_posix()


# ------------------------------------------------------------------ site
def site():
    (DOCS / "fonts").mkdir(parents=True, exist_ok=True)
    for f in (ROOT / "web" / "fonts").iterdir():
        shutil.copy2(f, DOCS / "fonts" / f.name)
    pkg = DOCS / "py" / "greencode"
    pkg.mkdir(parents=True, exist_ok=True)
    for f in ("__init__.py", "config.py", "analyzer.py", "fixer.py"):
        shutil.copy2(ROOT / "greencode" / f, pkg / f)
    sys.path.insert(0, str(ROOT))
    from greencode import scenarios
    en = {"siparis_raporu": "Order report (N+1)", "yoklama_kontrol": "Attendance check",
          "rota_raporu": "Route count", "fiyat_listesi": "Price list"}
    ornekler = [{"tr": s["baslik"], "en": en.get(s["giris"], s["baslik"]), "kod": s["kod"]}
                for s in sorted(scenarios.SCENARIOS, key=lambda s: s["id"] != "liste-arama")]
    ornekler.append({"tr": "Karışık örnek dosya", "en": "Mixed example file",
                     "kod": (ROOT / "ornekler" / "israfli_ornek.py").read_text("utf-8")})
    (DOCS / "py" / "ornekler.json").write_text(json.dumps(ornekler, ensure_ascii=False, indent=1), "utf-8")
    (DOCS / ".nojekyll").write_text("")            # GitHub Pages __init__.py dosyasını gizlemesin
    print("site    docs/ güncellendi")


# ------------------------------------------------------------------ QR
def qr():
    try:
        import segno
    except ImportError:
        sys.exit("QR için: pip install segno")
    QR_DIR.mkdir(exist_ok=True)
    hedefler = {
        "qr-proje-sayfasi": AYAR["site_url"],
        "qr-kodunu-dene": AYAR["site_url"] + "#dene",
        "qr-kaynak-kod": AYAR["repo_url"],
        "qr-try-en": AYAR["site_url"] + "?lang=en#dene",
    }
    for ad, url in hedefler.items():
        q = segno.make(url, error="q", micro=False)
        q.save(QR_DIR / f"{ad}.svg", scale=10, border=0, dark="#18211C", light=None, svgclass=None, lineclass=None)
        q.save(QR_DIR / f"{ad}.png", scale=24, border=4, dark="#18211C", light="#FFFFFF")
        print(f"qr      {ad:20} → {url}  (sürüm {q.version}, {q.error})")
    (QR_DIR / "adresler.txt").write_text("\n".join(f"{k}: {v}" for k, v in hedefler.items()) + "\n", "utf-8")


# ------------------------------------------------------------------ PDF
def pdf(sadece=None):
    PDF_DIR.mkdir(exist_ok=True)
    ONIZLEME.mkdir(exist_ok=True)
    httpd, base = sunucu()
    profil = tempfile.mkdtemp(prefix="yk-chrome-")
    try:
        for kaynak, cikti in BELGELER:
            if (sadece and sadece not in kaynak) or not (KAYNAK / kaynak).exists():
                continue
            yol = render_html(kaynak)
            chrome(["--no-pdf-header-footer", f"--print-to-pdf={PDF_DIR / cikti}", base + yol], profil)
            print(f"pdf     {cikti}")
        if not sadece or "brosur" in sadece:
            for ad in ("02-brosur-A5-TR.pdf", "03-brochure-A5-EN.pdf"):
                if (PDF_DIR / ad).exists():
                    a4_ikili(PDF_DIR / ad)
        onizlemeler()
    finally:
        httpd.shutdown()
        shutil.rmtree(profil, ignore_errors=True)
        shutil.rmtree(KAYNAK / "_render", ignore_errors=True)


def a4_ikili(a5_pdf: Path):
    """A5 broşürü, ucuz baskı için A4 yatay sayfaya yan yana iki kopya yerleştirir."""
    try:
        import pymupdf
    except ImportError:
        print("        (A4 dizgisi atlandı: pip install pymupdf)")
        return
    src = pymupdf.open(a5_pdf)
    out = pymupdf.open()
    w, h = 842, 595                                   # A4 yatay, pt
    for i in range(len(src)):
        p = out.new_page(width=w, height=h)
        for k in (0, 1):
            p.show_pdf_page(pymupdf.Rect(k * w / 2, 0, (k + 1) * w / 2, h), src, i)
        p.draw_line((w / 2, 0), (w / 2, 14), color=(.6, .6, .6), width=.4)          # kesim işaretleri
        p.draw_line((w / 2, h - 14), (w / 2, h), color=(.6, .6, .6), width=.4)
    hedef = a5_pdf.with_name(a5_pdf.stem.replace("A5", "A4-2li-baski") + ".pdf")
    out.save(hedef, garbage=3, deflate=True)
    print(f"pdf     {hedef.name}")


def onizlemeler():
    try:
        import pymupdf
    except ImportError:
        return
    for f in sorted(PDF_DIR.glob("*.pdf")):
        d = pymupdf.open(f)
        for i, page in enumerate(d):
            zoom = 1100 / max(page.rect.width, page.rect.height)
            page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).save(ONIZLEME / f"{f.stem}-s{i + 1}.png")


# ------------------------------------------------------------------ film
def film():
    if not shutil.which("ffmpeg"):
        sys.exit("Film için ffmpeg gerekir.")
    if not FILM_SRC.exists():
        sys.exit(f"Özgün film bulunamadı: {FILM_SRC}  (YK_FILM ortam değişkeniyle yolu verin)")
    FILM_DIR.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="yk-film-"))
    httpd, base = sunucu()
    profil = tempfile.mkdtemp(prefix="yk-chrome-")
    try:
        sure = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                     str(FILM_SRC)], capture_output=True, text=True, check=True).stdout)
        # 1) Kapanış kartının arka planı: filmin son sahnesi (logo ve alt satır yerinde kalsın).
        #    Özgün film son 0,5 s'de karardığı için kare ondan önce alınır.
        (KAYNAK / "_render").mkdir(exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(sure - 1.0), "-i", str(FILM_SRC), "-frames:v", "1",
                        str(KAYNAK / "_render" / "son-kare.png")], check=True)
        for ad, cikti in (("film-kapanis.html", "kapanis.png"), ("film-yama.html", "yama.png")):
            chrome([f"--screenshot={tmp / cikti}", "--window-size=1920,1080",
                    "--default-background-color=00000000", base + render_html(ad)], profil)
        # 2) "Gerçek ölçüm." → "Canlı ölçüm." (ölçüm tahmini modda yapıldı). Özgün metin 40,0 s'de
        #    ~0,3 s'de belirip 52,1–52,5 s'de kayboluyor; yama aynı zamanlamayı izler.
        #    Ardından, özgün kararma başlamadan, 0,8 s geçişle QR kapanış kartı.
        kapanis_s = 9
        gecis = sure - 1.4
        toplam = gecis + kapanis_s
        sahne = (
            "[0:v]drawbox=x=598:y=124:w=290:h=72:color=0x18211C@1:t=fill:enable='between(t,40.02,52.52)'[a0];"
            "[1:v]format=rgba,fade=t=in:st=40.0:d=0.3:alpha=1,fade=t=out:st=52.12:d=0.38:alpha=1[yama];"
            "[a0][yama]overlay=0:0:enable='between(t,40.0,52.55)',fps=30,format=yuv420p,setsar=1,settb=1/30[film];"
            f"[2:v]trim=duration={kapanis_s},fps=30,format=yuv420p,setsar=1,settb=1/30[kart];"
            f"[film][kart]xfade=transition=fade:duration=0.8:offset={gecis}[v];"
            f"[0:a]afade=t=out:st={sure - 2.5}:d=2.5,apad=whole_dur={toplam}[a]"
        )
        tam = FILM_DIR / "yesil-kod-film-qr.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(FILM_SRC),
                        "-loop", "1", "-framerate", "30", "-t", str(sure), "-i", str(tmp / "yama.png"),
                        "-loop", "1", "-framerate", "30", "-t", str(kapanis_s), "-i", str(tmp / "kapanis.png"),
                        "-filter_complex", sahne, "-map", "[v]", "-map", "[a]",
                        "-t", str(toplam),
                        "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(tam)], check=True)
        print(f"film    {tam.name}")
        # 3) Stant ekranı için sessiz, 10 kez tekrarlanan döngü (bazı TV'ler tek dosyayı döngüye almaz)
        dongu = FILM_DIR / "yesil-kod-stant-dongu-sessiz.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-stream_loop", "9", "-i", str(tam), "-an",
                        "-c:v", "copy", "-movflags", "+faststart", str(dongu)], check=True)
        print(f"film    {dongu.name}")
        # 4) Site için hafif sürüm, kapak karesi ve İngilizce altyazı
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tam), "-c:v", "libx264", "-preset", "slow",
                        "-crf", "30", "-maxrate", "1200k", "-bufsize", "2400k", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(DOCS / "film.mp4")], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "25.5", "-i", str(FILM_SRC), "-frames:v", "1",
                        "-q:v", "3", str(DOCS / "film-kapak.jpg")], check=True)
        shutil.copy2(KAYNAK / "film-en.vtt", DOCS / "film-en.vtt")
        shutil.copy2(KAYNAK / "film-en.vtt", FILM_DIR / "yesil-kod-film-en.vtt")
        print("film    docs/film.mp4, docs/film-kapak.jpg, docs/film-en.vtt")
    finally:
        httpd.shutdown()
        shutil.rmtree(profil, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(KAYNAK / "_render", ignore_errors=True)


if __name__ == "__main__":
    adim = sys.argv[1] if len(sys.argv) > 1 else "hepsi"
    if adim in ("site", "hepsi"):
        site()
    if adim in ("qr", "hepsi"):
        qr()
    if adim in ("pdf", "hepsi"):
        pdf(sys.argv[2] if len(sys.argv) > 2 else None)
    if adim in ("film", "hepsi"):
        film()
