"""Kural kataloğu: 113 kuralın basılabilir A4 belgesi (Türkçe ve İngilizce).

Sitedeki Kurallar sayfasıyla aynı veriden (hazirla.kural_verisi) üretilir: her kural için
neden enerji harcadığı, israflı ve verimli örnek, ölçüm sonucu, ne zaman sorun olmadığı
ve kaynağı. Sayfaları Chrome böler; sayfa numaraları sonradan pymupdf ile eklenir.
"""
from __future__ import annotations

import html
import os
import statistics

E = html.escape

METIN = {
    "tr": {
        "lang": "tr", "ust": "KURAL KATALOĞU · COP31 YEŞİL BÖLGE · ANTALYA 2026",
        "baslik": "Enerji israf eden 113 kod kalıbı, ölçümleriyle",
        "ozet_k": "ÖZET",
        "ozet": lambda n, olc, es, rnd, un, oto: (
            f"Yeşil Kod’un aradığı <b>{n} kalıbın</b> her biri için bir israflı ve bir verimli örnek yazıldı. "
            f"İkisi aynı girdiyle çalıştırıldı, çıktıları karşılaştırıldı, süreleri ve bellek kullanımları ölçüldü. "
            f"<b>{olc} kural ölçüldü</b>; çıktısı karşılaştırılabilen {es} kuralın hepsinde iki sürüm birebir aynı sonucu verdi"
            + (f", {rnd} kuralın çıktısı rastgele" if rnd else "") +
            f". {un} kural veritabanı sunucusu, GPU ya da ağ gerektirdiği için ölçülmedi; nedenleri yazılı. "
            f"<b>{oto} kalıbı</b> motor kendisi düzeltir; onların düzeltmesi de aynı yöntemle sınandı."),
        "dagilim": "ÖLÇÜLEN KAZANÇ (israflı sürümün süresi ÷ verimli sürümün süresi)",
        "kova": ["100× ve üstü", "10–100×", "2–10×", "1,1–2×", "Hızda fark yok, bellekte kazanç", "Hızda fark yok", "Verimli sürüm yavaş"],
        "kural": "kural",
        "nasil": "Nasıl okunur?",
        "nasil_l": [
            "<b>Önem</b>: <i>yüksek</i> veri büyüdükçe katlanan israf, <i>orta</i> belirgin israf, <i>bilgi</i> küçük ama kolay kazanç.",
            "<b>Motor düzeltir</b>: Yeşil Kod bu kalıbı kodda kendisi yeniden yazar; diğerleri için öneri verir.",
            "<b>Kazanç</b>: israflı sürümün süresinin verimli sürümün süresine oranı (5 turun ortancası). Bekleme kurallarında süre aynıdır; oran işlemci süresinden alınır.",
            "<b>Fark yok</b> ya da <b>yavaş</b> çıkan sonuçlar da yazıldı; nedeni her kuralın altındaki notta.",
            "Kodlarda <span class='hk'>vurgulu satırlar</span> iki sürüm arasında değişen satırlardır.",
        ],
        "ortam": lambda e: f"Ölçüm: {e['islemci'] or e['sistem']}, Python {e['python']}, {tarih(e['tarih'], 'tr')}. "
                           "Enerji tahmini işlemci süresiyle orantılıdır; aynı işlemcide oran enerji oranına eşittir.",
        "gruplar": "Gruplar", "qr": "Her kuralı telefonunda aç, kendi cihazında ölç.",
        "neden": "Neden enerji harcar?", "istisna": "Ne zaman sorun değil?", "is": "Yapılan iş",
        "kotu": "İsraflı", "iyi": "Verimli", "olcum": "Ölçüm", "olculmedi": "Ölçülmedi",
        "sure": "süre", "islemci": "işlemci", "bellek": "bellek", "dosya": "dosya", "ayni": "aynı sonuç ✓", "rastgele": "çıktı rastgele",
        "kaynak": "Kaynak", "motor": "Motor düzeltir", "oneri": "Öneri verir", "motor_ok": lambda k: f"Motorun düzeltmesi de aynı sonucu verdi ({k}).",
        "sev": {"yüksek": "yüksek", "orta": "orta", "bilgi": "bilgi"},
        "gain": {"win": "{} hızlı", "cpu": "{} az işlemci", "mem": "{} az bellek", "flat": "fark yok", "loss": "{} yavaş", "na": "ölçülmedi"},
        "yontem": "Ölçüm yöntemi ve sınırlar",
        "yontem_l": [
            "Her kuralın israflı (<code>ornekler/kurallar/YKxxx.py</code>) ve verimli (<code>iyi/YKxxx.py</code>) örneği aynı adla ve aynı girdiyle çalıştırılır. Girdi her iki sürüm için aynı tohumla üretilir.",
            "Önce çıktılar karşılaştırılır: dönüş değeri ya da bıraktığı iz (veritabanı, dosya, ekran çıktısı). Aynı değilse ölçüm yapılmaz.",
            "Süre ve işlemci süresi iki sürüm sırayla (A, B, A, B…) ölçülerek alınır; makinenin anlık yükü iki tarafı eşit etkiler. Her tur yaklaşık 60 ms sürer; sonuç 5 turun ortancasıdır.",
            "Girdisini değiştiren örneklerde her çağrıdan önce girdi yeniden kurulur ve kurulum ölçüme girmez. Önbellekler her çağrıdan önce temizlenir.",
            "Bellek tepe değeri ayrı bir çalıştırmada tracemalloc ile ölçülür; yalnızca çağrı sırasında ayrılan bellek sayılır.",
            "Veritabanı kuralları bellekteki (bağlantı ve commit kuralları diskteki) SQLite ile ölçüldü. Ağ üzerindeki bir veritabanında her sorgu ayrıca bir gidiş-dönüş ekler; gerçek fark genellikle daha büyüktür.",
            "Herkes tekrarlayabilir: <code>python -m greencode kanit</code> bütün ölçümleri yeniden alır. Sitede her kuralın sayfasından aynı ölçüm tarayıcıda yapılabilir.",
        ],
        "hizsiz": "Hızda kazanç göstermeyen kurallar",
        "hizsiz_a": "Bu kuralların değeri bellekte, doğrulukta ya da okunabilirliktedir. Ölçüm bunu gizlemeden gösteriyor.",
        "olcmeyen": "Ölçülmeyen kurallar ve nedenleri",
        "alt": "Yeşil Kod · Kural kataloğu", "sayfa": "s.",
    },
    "en": {
        "lang": "en", "ust": "RULE CATALOGUE · COP31 GREEN ZONE · ANTALYA 2026",
        "baslik": "113 energy-wasting code patterns, measured",
        "ozet_k": "SUMMARY",
        "ozet": lambda n, olc, es, rnd, un, oto: (
            f"For each of the <b>{n} patterns</b> Yeşil Kod looks for, a wasteful and an efficient example were written. "
            f"Both ran on the same input; their outputs were compared and their time and memory measured. "
            f"<b>{olc} rules were measured</b>; in all {es} whose output could be compared, both versions gave exactly the same result"
            + (f", and {rnd} has a random output" if rnd else "") +
            f". {un} rules need a database server, a GPU or the network, so they were not measured; the reasons are listed. "
            f"The engine fixes <b>{oto} patterns</b> by itself; its fixes were tested the same way."),
        "dagilim": "MEASURED GAIN (wasteful version’s time ÷ efficient version’s time)",
        "kova": ["100× and above", "10–100×", "2–10×", "1.1–2×", "No time difference, memory gain", "No time difference", "Efficient version slower"],
        "kural": "rules",
        "nasil": "How to read it",
        "nasil_l": [
            "<b>Severity</b>: <i>high</i> waste that multiplies as data grows, <i>medium</i> clear waste, <i>info</i> small but easy gain.",
            "<b>Engine fixes it</b>: Yeşil Kod rewrites this pattern in the code by itself; for the others it gives advice.",
            "<b>Gain</b>: the wasteful version’s time divided by the efficient version’s (median of 5 rounds). For waiting rules the time is the same, so the ratio comes from CPU time.",
            "Results showing <b>no difference</b> or <b>slower</b> are listed too; the reason is in the note under each rule.",
            "<span class='hk'>Highlighted lines</span> in the code are the lines that differ between the two versions.",
        ],
        "ortam": lambda e: f"Measured on {e['islemci'] or e['sistem']}, Python {e['python']}, {tarih(e['tarih'], 'en')}. "
                           "Estimated energy is proportional to CPU time; on the same processor the ratio equals the energy ratio.",
        "gruplar": "Groups", "qr": "Open any rule on your phone and measure it on your own device.",
        "neden": "Why does it waste energy?", "istisna": "When is it fine?", "is": "Work done",
        "kotu": "Wasteful", "iyi": "Efficient", "olcum": "Measured", "olculmedi": "Not measured",
        "sure": "time", "islemci": "CPU", "bellek": "memory", "dosya": "file", "ayni": "same result ✓", "rastgele": "random output",
        "kaynak": "Source", "motor": "Engine fixes it", "oneri": "Gives advice", "motor_ok": lambda k: f"The engine’s fix gave the same result too ({k}).",
        "sev": {"yüksek": "high", "orta": "medium", "bilgi": "info"},
        "gain": {"win": "{} faster", "cpu": "{} less CPU", "mem": "{} less memory", "flat": "no difference", "loss": "{} slower", "na": "not measured"},
        "yontem": "Measurement method and limits",
        "yontem_l": [
            "Each rule’s wasteful (<code>ornekler/kurallar/YKxxx.py</code>) and efficient (<code>iyi/YKxxx.py</code>) example share a name and run on the same input, generated with the same seed for both.",
            "Outputs are compared first: the return value or the trace left behind (database, file, screen output). If they differ, nothing is measured.",
            "Time and CPU time are measured alternately (A, B, A, B…) so momentary machine load affects both sides equally. Each round takes about 60 ms; the result is the median of 5 rounds.",
            "When an example changes its input, the input is rebuilt before every call and the rebuild is not timed. Caches are cleared before every call.",
            "Peak memory is measured in a separate run with tracemalloc; only memory allocated during the call counts.",
            "Database rules were measured on in-memory SQLite (connection and commit rules on an SQLite file). Over a network every query also adds a round trip, so the real gap is usually larger.",
            "Anyone can repeat it: <code>python -m greencode kanit</code> re-runs every measurement. On the website, each rule’s page runs the same measurement in the browser.",
        ],
        "hizsiz": "Rules that show no speed gain",
        "hizsiz_a": "The value of these rules lies in memory, correctness or readability. The measurement shows that openly.",
        "olcmeyen": "Rules not measured, and why",
        "alt": "Yeşil Kod · Rule catalogue", "sayfa": "p.",
    },
}


def tarih(t, dil):
    y, a, g = t.split("-")
    aylar = {"tr": "Ocak Şubat Mart Nisan Mayıs Haziran Temmuz Ağustos Eylül Ekim Kasım Aralık",
             "en": "January February March April May June July August September October November December"}[dil].split()
    return f"{int(g)} {aylar[int(a) - 1]} {y}"


def sayi(x, d, dil):
    s = f"{x:,.{d}f}"
    return s.replace(",", "\0").replace(".", ",").replace("\0", ".") if dil == "tr" else s


def kat(k, dil):
    return sayi(k, 0 if k >= 100 else 1 if k >= 10 else 2, dil) + "×"


def sure(s, dil):
    if s >= 1:
        return sayi(s, 2, dil) + " s"
    if s >= 1e-3:
        return sayi(s * 1e3, 1, dil) + " ms"
    return sayi(s * 1e6, 0 if s >= 1e-5 else 1, dil) + " µs"


def bayt(b, dil):
    if b >= 1048576:
        return sayi(b / 1048576, 1, dil) + " MB"
    if b >= 1024:
        return sayi(b / 1024, 1, dil) + " KB"
    return sayi(b, 0, dil) + " B"


def kazanc(o):
    """Sitedeki gainOf ile aynı sınıflandırma."""
    if not o:
        return "na", None
    if o["kat"] >= 1.1:
        return ("cpu" if o["olcut"] == "islemci" else "win"), o["kat"]
    if (o.get("bellek_kat") or 0) >= 2 and o["kotu"]["bellek_b"] - o["iyi"]["bellek_b"] >= 4096:
        return "mem", o["bellek_kat"]       # birkaç düzine baytlık fark kazanç sayılmaz
    if o["kat"] > 0.9:
        return "flat", o["kat"]
    return "loss", 1 / o["kat"]


def etiket(o, dil):
    sinif, k = kazanc(o)
    return sinif, METIN[dil]["gain"][sinif].format(kat(k, dil) if k else "")


def _kod(kaynak, diger):
    d = {s.strip() for s in diger.splitlines()}
    return "".join(f'<span class="hk">{E(s) or " "}</span>' if s.strip() and s.strip() not in d else f"<span>{E(s) or ' '}</span>"
                   for s in kaynak.rstrip("\n").splitlines())


def _kural(r, dil, M):
    t = (lambda a: r[a + "_en"]) if dil == "en" else (lambda a: r[a])
    sinif, et = etiket(r.get("olcum"), dil)
    o = r.get("olcum")
    if o:
        A, B = o["kotu"], o["iyi"]
        parca = [f"{M['sure']} {sure(A['sure_s'], dil)} → {sure(B['sure_s'], dil)}"]
        if o["olcut"] == "islemci":
            parca.append(f"{M['islemci']} {sure(A['islemci_s'], dil)} → {sure(B['islemci_s'], dil)}")
        if "bellek_b" in A:
            parca.append(f"{M['bellek']} {bayt(A['bellek_b'], dil)} → {bayt(B['bellek_b'], dil)}")
        if A.get("boyut_b"):
            parca.append(f"{M['dosya']} {bayt(A['boyut_b'], dil)} → {bayt(B['boyut_b'], dil)}")
        parca.append(M["ayni"] if o["esdeger"] else M["rastgele"])
        notu = o.get("not_en" if dil == "en" else "not")
        motor = o.get("motor")
        olcum = (f'<div class="m"><b>{M["olcum"]}</b>{" · ".join(E(p) for p in parca)}'
                 + (f'<span class="n">{E(notu)}</span>' if notu else "")
                 + (f'<span class="n">{E(M["motor_ok"](kat(motor["kat"], dil)))}</span>' if motor and motor.get("esdeger") else "")
                 + "</div>")
    else:
        olcum = f'<div class="m na"><b>{M["olculmedi"]}</b>{E(t("olculmedi"))}</div>'
    url = r["url"].replace("https://", "")
    return f'''<div class="r">
  <div class="rh"><b class="k">{r["kural"]}</b><span class="sev s-{ {"yüksek": "y", "orta": "o", "bilgi": "b"}[r["onem"]] }">{M["sev"][r["onem"]]}</span>
    <span class="tag{' auto' if r["otomatik"] else ''}">{M["motor"] if r["otomatik"] else M["oneri"]}</span><span class="g {sinif}">{E(et)}</span></div>
  <h3>{E(t("baslik"))}</h3>
  <p class="adv">{E(t("oneri"))}</p>
  <div class="two">
    <div><h4>{M["neden"]}</h4><p>{E(t("neden"))}</p><p class="cx"><span>{M["is"]}</span>{E(t("karmasiklik"))}</p></div>
    <div><h4>{M["istisna"]}</h4><p>{E(t("istisna"))}</p></div>
  </div>
  <div class="codes"><div class="c bad"><i>{M["kotu"]}</i><pre>{_kod(r["ornek"], r["iyi"])}</pre></div>
    <div class="c good"><i>{M["iyi"]}</i><pre>{_kod(r["iyi"], r["ornek"])}</pre></div></div>
  {olcum}
  <div class="src">{M["kaynak"]}: {E(r["kaynak"])} · <span>{E(url)}</span></div>
</div>'''


def html_uret(veri, dil, ayar):
    M = METIN[dil]
    K = veri["kurallar"]
    olc = [r for r in K if r.get("olcum")]
    es = sum(1 for r in olc if r["olcum"]["esdeger"] is True)
    rnd = sum(1 for r in olc if r["olcum"]["esdeger"] is None)
    oto = sum(1 for r in K if r["otomatik"])
    t = (lambda r, a: r[a + "_en"]) if dil == "en" else (lambda r, a: r[a])

    def kova(o):
        s, k = kazanc(o)
        if s in ("win", "cpu"):
            return 0 if k >= 100 else 1 if k >= 10 else 2 if k >= 2 else 3
        return {"mem": 4, "flat": 5, "loss": 6}[s]
    sayac = [0] * 7
    for r in olc:
        sayac[kova(r["olcum"])] += 1
    en_cok = max(sayac)
    dagilim = "".join(f'<div class="dl">{E(ad)}</div><div class="db"><i class="k{i}" style="width:{n / en_cok * 100:.1f}%"></i><em>{n}</em></div>'
                      for i, (ad, n) in enumerate(zip(M["kova"], sayac)))
    ortanca = statistics.median(r["olcum"]["kat"] for r in olc)
    gruplar = "".join(
        f'<div><i>{i:02d}</i><span>{E(v[dil])}</span><b>{sum(1 for r in K if r["kategori"] == k)}</b></div>'
        for i, (k, v) in enumerate(veri["kategoriler"].items(), 1))
    bolumler = []
    for i, (k, v) in enumerate(veri["kategoriler"].items(), 1):
        kk = [r for r in K if r["kategori"] == k]
        bolumler.append(f'<section class="grup"><h2><i>{i:02d}</i>{E(v[dil])}<small>{len(kk)} {M["kural"]}</small></h2>'
                        + "".join(_kural(r, dil, M) for r in kk) + "</section>")
    hizsiz = [r for r in olc if kazanc(r["olcum"])[0] in ("mem", "flat", "loss")]
    hizsiz_satir = "".join(
        f'<tr><td class="mono">{r["kural"]}</td><td>{E(t(r, "baslik"))}</td><td class="g {kazanc(r["olcum"])[0]}">{E(etiket(r["olcum"], dil)[1])}</td>'
        f'<td>{E(r["olcum"].get("not_en" if dil == "en" else "not") or "")}</td></tr>' for r in hizsiz)
    olcmeyen_satir = "".join(
        f'<tr><td class="mono">{r["kural"]}</td><td>{E(t(r, "baslik"))}</td><td>{E(t(r, "olculmedi"))}</td></tr>'
        for r in K if not r.get("olcum"))
    qr = "qr-rules-en.svg" if dil == "en" else "qr-kurallar.svg"
    site = ayar["site_url"].replace("https://", "").rstrip("/") + ("/?lang=en#kurallar" if dil == "en" else "/#kurallar")
    return f'''<!doctype html>
<html lang="{M["lang"]}">
<head>
<meta charset="utf-8">
<title>Yeşil Kod · {"Rule catalogue" if dil == "en" else "Kural kataloğu"}</title>
<link rel="stylesheet" href="/stant/kaynak/ortak.css">
<style>{CSS}</style>
</head>
<body>
<div class="kapak">
  <div class="bar"><div class="word">yeşil<span>kod</span></div><span>{M["ust"]}</span></div>
  <h1>{M["baslik"]}</h1>
  <div class="meta"><b>{E(ayar["proje_adi_en" if dil == "en" else "proje_adi"])}</b><br>{E(ayar["kurum_en" if dil == "en" else "kurum"])} · {E(" · ".join(ayar["ekip"]))}</div>
  <div class="abs"><div><div class="k">{M["ozet_k"]}</div><p>{M["ozet"](len(K), len(olc), es, rnd, len(K) - len(olc), oto)}</p></div>
    <div class="x">{kat(ortanca, dil)}<small>{"median measured gain" if dil == "en" else "ölçülen kazancın ortancası"}</small></div></div>
  <div class="k2">{M["dagilim"]}</div>
  <div class="dag">{dagilim}</div>
  <div class="kgrid">
    <div><h2 class="h">{M["nasil"]}</h2><ul class="l">{"".join(f"<li>{x}</li>" for x in M["nasil_l"])}</ul>
      <p class="fine">{E(M["ortam"](veri["olcum_ortami"]))}</p></div>
    <div class="qrk"><div class="qr"><img src="/stant/qr/{qr}" alt="QR"></div><p>{M["qr"]}</p><p class="u">{E(site)}</p></div>
  </div>
  <h2 class="h">{M["gruplar"]}</h2>
  <div class="gt">{gruplar}</div>
</div>
{"".join(bolumler)}
<section class="son">
  <h2 class="h">{M["yontem"]}</h2>
  <ul class="l">{"".join(f"<li>{x}</li>" for x in M["yontem_l"])}</ul>
  <h2 class="h">{M["hizsiz"]}</h2><p class="t">{M["hizsiz_a"]}</p>
  <table class="lt">{hizsiz_satir}</table>
  <h2 class="h">{M["olcmeyen"]}</h2>
  <table class="lt">{olcmeyen_satir}</table>
</section>
</body>
</html>'''


CSS = """
@page{size:210mm 297mm;margin:13mm 14mm 15mm}
body{font:400 8.2pt/1.42 var(--sans);color:var(--ink2)}
b{color:var(--ink);font-weight:600}
code{font:400 6.9pt var(--mono);color:var(--ink)}
.kapak{break-after:page}
.bar{display:flex;justify-content:space-between;align-items:center;padding-bottom:3.5mm;border-bottom:.35mm solid var(--ink)}
.bar .word{font-size:15pt}
.bar > span{font:600 6.4pt/1 var(--mono);letter-spacing:.08em;color:var(--ink3)}
h1{font:700 22pt/1.12 var(--sans);letter-spacing:-.015em;color:var(--ink);margin-top:7mm;max-width:165mm}
.meta{font:400 8.4pt/1.45 var(--sans);color:var(--ink3);margin-top:3mm}
.abs{margin-top:5mm;background:var(--ink);color:var(--paper);border-radius:3mm;padding:5mm 6.5mm;display:grid;grid-template-columns:1fr 38mm;gap:7mm;align-items:center}
.abs p{font:400 9pt/1.5 var(--sans);color:var(--mist2)}
.abs p b{color:var(--paper)}
.abs .k{font:600 6.4pt/1 var(--mono);letter-spacing:.08em;color:var(--leaf);margin-bottom:2.5mm}
.abs .x{font:700 30pt/.95 var(--mono);font-stretch:112.5%;letter-spacing:-.05em;color:var(--leaf);text-align:right}
.abs .x small{display:block;font:400 7.4pt/1.35 var(--sans);letter-spacing:0;color:var(--mist2);margin-top:2mm}
.k2{font:600 6.4pt/1 var(--mono);letter-spacing:.07em;color:var(--ink3);margin-top:6mm}
.dag{display:grid;grid-template-columns:54mm 1fr;gap:1.4mm 4mm;align-items:center;margin-top:3mm}
.dl{font:400 8pt/1.2 var(--sans);color:var(--ink2)}
.db{position:relative;height:4.2mm;background:var(--paper);border-radius:.8mm}
.db i{position:absolute;left:0;top:0;bottom:0;border-radius:.8mm;background:#2F8F5F;min-width:.6mm}
.db i.k1{background:#3E9C6C}.db i.k2{background:#66B48A}.db i.k3{background:#9CCBAE}.db i.k4{background:#A9B8AE}.db i.k5{background:#C9D3CC}.db i.k6{background:#C4601A}
.db em{position:absolute;left:calc(100% + 2mm);top:50%;transform:translateY(-50%);font:600 7.6pt var(--mono);font-style:normal;color:var(--ink)}
.dag .db{margin-right:10mm}
.kgrid{display:grid;grid-template-columns:1fr 40mm;gap:8mm;margin-top:6mm;align-items:start}
h2.h{font:700 11pt/1.2 var(--sans);color:var(--ink);margin-top:5mm}
.kgrid h2.h{margin-top:0}
ul.l{list-style:none;margin-top:2mm;display:flex;flex-direction:column;gap:1.1mm;font:400 8.2pt/1.42 var(--sans)}
ul.l li{padding-left:3.4mm;position:relative}
ul.l li::before{content:"";position:absolute;left:0;top:1.65mm;width:1.3mm;height:1.3mm;border-radius:50%;background:var(--moss)}
.fine{font:400 7pt/1.4 var(--sans);color:var(--ink3);margin-top:2.5mm}
.qrk .qr{border:.25mm solid var(--rule);border-radius:1.5mm;padding:2mm}
.qrk p{font:400 7.6pt/1.35 var(--sans);margin-top:2mm}
.qrk p.u{font:500 6.4pt/1.3 var(--mono);color:var(--ink3);word-break:break-all;margin-top:1mm}
table{width:100%;border-collapse:collapse}
.gt{display:grid;grid-template-columns:repeat(3,1fr);gap:0 6mm;margin-top:2mm}
.gt div{display:flex;gap:2mm;align-items:baseline;padding:1.3mm 0;border-bottom:.2mm solid var(--rule);font:400 8pt/1.3 var(--sans)}
.gt i{font:700 7pt var(--mono);font-style:normal;color:var(--moss)}
.gt span{flex:1;color:var(--ink);font-weight:600}
.gt b{font:600 8pt var(--mono);color:var(--ink3)}
.lt td.mono{font:400 6.6pt/1.45 var(--mono);color:var(--ink3)}
.grup{break-before:page}
.grup h2{font:700 15pt/1.15 var(--sans);color:var(--ink);display:flex;gap:3mm;align-items:baseline;padding-bottom:2.5mm;border-bottom:.35mm solid var(--ink);margin-bottom:1mm}
.grup h2 i{font:700 10pt/1 var(--mono);font-style:normal;color:var(--moss)}
.grup h2 small{margin-left:auto;font:600 7pt var(--mono);color:var(--ink3)}
.r{break-inside:avoid;padding:3.4mm 0 3.6mm;border-bottom:.2mm solid var(--rule)}
.rh{display:flex;gap:1.6mm;align-items:center}
.rh .k{font:700 8.4pt var(--mono)}
.sev,.tag,.g{font:600 6.2pt/1 var(--mono);padding:.8mm 1.4mm;border-radius:.8mm;white-space:nowrap}
.s-y{background:var(--amber-tint);color:var(--amber-ink)} .s-o{background:#E9E2C9;color:#6B5714} .s-b{background:var(--paper);color:var(--ink2)}
.tag{background:var(--paper);color:var(--ink2)} .tag.auto{background:var(--moss-tint);color:var(--moss-ink)}
.g{margin-left:auto;font-size:7.6pt;padding:1mm 1.8mm}
.g.win,.g.cpu,.g.mem{background:var(--moss-tint);color:var(--moss-ink)}
.g.flat,.g.na{background:var(--paper);color:var(--ink3)} .g.loss{background:var(--amber-tint);color:var(--amber-ink)}
.r h3{font:700 10.6pt/1.25 var(--sans);color:var(--ink);margin-top:1.6mm}
.adv{margin-top:.8mm;color:var(--ink2)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:5mm;margin-top:2mm}
h4{font:600 6.4pt/1 var(--mono);letter-spacing:.05em;text-transform:uppercase;color:var(--ink3);margin-bottom:.9mm}
.two p{font-size:7.7pt;line-height:1.4}
.cx{margin-top:1mm;font:600 7.2pt var(--mono);color:var(--ink)}
.cx span{font:600 5.8pt var(--mono);letter-spacing:.05em;text-transform:uppercase;color:var(--ink3);margin-right:1.6mm}
.codes{display:grid;grid-template-columns:1fr 1fr;gap:3mm;margin-top:2.2mm}
.c{border:.2mm solid var(--rule);border-radius:1.2mm;overflow:hidden;min-width:0}
.c i{display:block;font:600 5.8pt/1 var(--mono);font-style:normal;letter-spacing:.06em;text-transform:uppercase;padding:1.2mm 2mm;background:var(--paper)}
.c.bad i{color:var(--amber-ink);box-shadow:inset .6mm 0 var(--amber)} .c.good i{color:var(--moss-ink);box-shadow:inset .6mm 0 #2F8F5F}
.c pre{font:400 6.3pt/1.5 var(--mono);font-stretch:75%;padding:1mm 0;white-space:pre-wrap;word-break:break-word}
.c pre span{display:block;padding:0 2mm 0 5mm;text-indent:-3mm}
.c.bad pre .hk{background:var(--amber-tint)} .c.good pre .hk{background:var(--moss-tint)}
span.hk{background:var(--moss-tint);padding:0 .8mm;border-radius:.6mm}
.m{margin-top:2mm;font:400 7.6pt/1.45 var(--sans);color:var(--ink2)}
.m b{font:600 6.2pt var(--mono);letter-spacing:.05em;text-transform:uppercase;color:var(--moss-ink);margin-right:1.8mm}
.m.na b{color:var(--ink3)}
.m .n{display:block;color:var(--ink3);margin-top:.4mm}
.src{margin-top:1.2mm;font:400 6.8pt/1.35 var(--sans);color:var(--ink3)}
.src span{font:400 6.2pt var(--mono);word-break:break-all}
.son{break-before:page}
.son h2.h:first-child{margin-top:0}
p.t{margin-top:1.2mm}
.lt{margin-top:2mm;font:400 7.4pt/1.35 var(--sans)}
.lt td{padding:1.1mm 2mm 1.1mm 0;border-bottom:.2mm solid var(--rule);vertical-align:top}
.lt td:nth-child(2){color:var(--ink);font-weight:600;width:48mm}
.lt td.g{font:600 6.6pt var(--mono);white-space:nowrap;background:none;padding:1.1mm 2mm 1.1mm 0;margin:0}
.lt td.g.loss{color:var(--amber-ink)} .lt td.g.mem{color:var(--moss-ink)} .lt td.g.flat{color:var(--ink3)}
"""


def _yazi_tipi():
    """Türkçe harfleri (ş, ğ, İ) olan bir yazı tipi; pymupdf'nin yerleşik Helvetica'sında yoklar."""
    for yol in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(yol):
            return {"fontname": "ykalt", "fontfile": yol}
    return {"fontname": "helv"}


def sayfa_numarasi(yol, dil):
    """Kapak dışındaki sayfaların altına belge adı ve sayfa numarası yazar."""
    import pymupdf
    M = METIN[dil]
    d = pymupdf.open(yol)
    n = len(d)
    for i, sayfa in enumerate(d):
        if i == 0:
            continue
        w, h = sayfa.rect.width, sayfa.rect.height
        renk = (0x55 / 255, 0x63 / 255, 0x5B / 255)
        yazi = dict(fontsize=6.5, color=renk, **_yazi_tipi())
        sayfa.insert_text((40, h - 22), M["alt"], **yazi)
        metin = f"{M['sayfa']} {i + 1} / {n}"
        genislik = pymupdf.Font(fontfile=yazi["fontfile"]).text_length(metin, 6.5) if "fontfile" in yazi \
            else pymupdf.get_text_length(metin, fontname="helv", fontsize=6.5)
        sayfa.insert_text((w - 40 - genislik, h - 22), metin, **yazi)
    gecici = str(yol) + ".tmp"
    d.save(gecici, garbage=3, deflate=True)
    d.close()
    os.replace(gecici, yol)
