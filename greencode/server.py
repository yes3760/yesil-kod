"""Demo sunucusu: yalnızca Python standart kütüphanesi, internet gerekmez.

GET  /                      canlı panel (web/index.html)
GET  /fonts/<dosya>         panel yazı tipleri (SIL OFL)
GET  /api/bilgi             ölçüm modu ve katsayılar
GET  /api/senaryolar        senaryolar + motorun ürettiği düzeltme ve fark (ölçümsüz)
POST /api/kanitla {id}      eşdeğerlik testi + iki sürümün ölçümü
GET  /api/yaris?id=...      canlı enerji yarışı (Server-Sent Events)
POST /api/analiz {kod}      statik analiz + otomatik düzeltme farkı (kod ÇALIŞTIRILMAZ)
GET  /api/ornek             analiz ekranı için örnek kod
"""
from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from . import analyzer, config, fixer, proof, scenarios
from .meter import EnergyMeter

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
_lock = threading.Lock()                 # ölçümler aynı anda çalışıp birbirini bozmasın
_state = {}


def meter():
    if "meter" not in _state:
        _state["meter"] = EnergyMeter()
    return _state["meter"]


def data():
    if "data" not in _state:
        _state["data"] = scenarios.build_data()
    return _state["data"]


def scenario_list():
    if "list" not in _state:
        out = []
        for s in scenarios.SCENARIOS:
            new, orig, fixes = fixer.fix(s["kod"])
            out.append({k: s[k] for k in ("id", "baslik", "kalip", "ozet", "gercek_hayat")}
                       | {"fark": fixer.side_by_side(orig, new), "duzeltmeler": [f.to_dict() for f in fixes]})
        _state["list"] = out
    return _state["list"]


class Handler(BaseHTTPRequestHandler):
    server_version = "YesilKod/2.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, body: bytes, ctype, status=200, cache=False):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if cache:
            self.send_header("Cache-Control", "max-age=86400")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status=200):
        self._send(json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8", status)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        if n > 200_000:
            raise ValueError("Gönderilen kod 200 KB sınırını aşıyor.")
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        u = urlparse(self.path)
        p = u.path
        if p in ("/", "/index.html"):
            return self._send((WEB / "index.html").read_bytes(), "text/html; charset=utf-8")
        if p.startswith("/fonts/"):
            f = (WEB / "fonts" / Path(p).name)
            if f.suffix == ".woff2" and f.is_file():
                return self._send(f.read_bytes(), "font/woff2", cache=True)
        if p == "/api/bilgi":
            return self._json(meter().info() | {"ai_aktif": bool(config.ANTHROPIC_API_KEY)})
        if p == "/api/senaryolar":
            return self._json(scenario_list())
        if p == "/api/ornek":
            return self._json({"kod": (ROOT / "ornekler" / "israfli_ornek.py").read_text("utf-8")})
        if p == "/api/yaris":
            return self._race(parse_qs(u.query).get("id", [""])[0])
        self._json({"hata": "Bulunamadı"}, 404)

    def _race(self, sid):
        try:
            s = scenarios.get(sid)
        except KeyError:
            return self._json({"hata": "Senaryo bulunamadı"}, 400)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        try:
            with _lock:
                for ev in proof.race(s["kod"], s["giris"], data(), meter()):
                    self.wfile.write(f"data: {json.dumps(ev, ensure_ascii=False)}\n\n".encode())
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        p = urlparse(self.path).path
        try:
            body = self._body()
            if p == "/api/kanitla":
                s = scenarios.get(body.get("id"))
                with _lock:
                    return self._json(proof.prove(s["kod"], s["giris"], data(), meter(),
                                                  measure=bool(body.get("olc", True))))
            if p == "/api/analiz":
                kod = body.get("kod", "")
                sonuc = analyzer.analyze(kod)
                if not sonuc["hata"]:
                    new, orig, fixes = fixer.fix(kod)
                    sonuc["fark"] = fixer.side_by_side(orig, new) if fixes else []
                    sonuc["duzeltmeler"] = [f.to_dict() for f in fixes]
                    if body.get("ai"):
                        sonuc["ai"] = analyzer.ai_suggestion(kod, sonuc["bulgular"])
                return self._json(sonuc)
            self._json({"hata": "Bulunamadı"}, 404)
        except KeyError:
            self._json({"hata": "Senaryo bulunamadı."}, 400)
        except Exception as e:                          # stantta panel çökmesin
            self._json({"hata": f"{type(e).__name__}: {e}"}, 500)


def serve(host=None, port=None, open_browser=True):
    host, port = host or config.HOST, port or config.PORT
    m = meter()
    print("\n  Yeşil Kod · Dijital Karbon Ayak İzi Optimizasyon Aracı")
    print(f"  Ölçüm      : {m.info()['mode_label']}")
    if m.mode == "tahmini":
        print("  (Linux'ta gerçek ölçüm için: sudo chmod -R a+r /sys/class/powercap/intel-rapl)")
    print(f"  Şebeke     : {config.CARBON_INTENSITY_G_PER_KWH:g} gCO2e/kWh (Türkiye)")
    print("  Hazırlanıyor…", end="", flush=True)
    data(); scenario_list()
    print(f"\r  Panel      : http://{host}:{port}        \n  Durdurmak için Ctrl+C\n")
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    if open_browser:
        import webbrowser
        threading.Timer(0.8, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Kapatıldı.")
