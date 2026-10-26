"""Analiz ekranında varsayılan olarak gösterilen örnek kod.
İçinde bilerek bırakılmış enerji israfı kalıpları var."""
import json
import re
import time


def siparis_raporu(db, siparisler):
    rapor = []
    for s in siparisler:
        musteri = db.execute("SELECT ad FROM musteri WHERE id = ?", (s["musteri_id"],)).fetchone()
        rapor.append((s["id"], musteri[0]))
    return rapor


def kayitli_mi(aranacaklar, kayit_dosyasi):
    kayitlar = [satir.strip() for satir in open(kayit_dosyasi)]
    return [k for k in aranacaklar if k in kayitlar]


def fiyatla(urunler, ayar_metni):
    sonuc = []
    for u in urunler:
        ayar = json.loads(ayar_metni)
        desen = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.]+$")
        if desen.match(u["eposta"]):
            sonuc.append(u["fiyat"] * (1 + ayar["kdv"]))
    return sonuc


def fib(n):
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)


def eslestir(ogrenciler, dersler):
    eslesme = []
    for o in ogrenciler:
        for d in dersler:
            if d["ogrenci_id"] == o["id"]:
                eslesme.append((o["ad"], d["ad"]))
    return eslesme


def siparis_bekle(api):
    while True:
        if api.yeni_siparis_var_mi():
            return api.siparisi_al()
        time.sleep(0.1)
