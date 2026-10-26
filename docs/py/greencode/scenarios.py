"""Demo senaryoları.

Her senaryo, gerçek projelerde sık görülen israflı bir kod parçasıdır.
Optimize sürümü elle YAZILMAZ: düzeltme motoru (fixer.py) üretir. Ardından
proof.py iki sürümü de çalıştırıp aynı sonucu verdiklerini doğrular ve
enerjilerini ölçer. Yani demo, aracın uçtan uca çalıştığının kanıtıdır.
"""
from __future__ import annotations

import json
import random
import re
import sqlite3


def build_data():
    """Senaryoların ortak verisi. Her çağrıda aynı veriyi üretir (sabit tohum)."""
    rng = random.Random(42)
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.executescript("""
    CREATE TABLE musteri(id INTEGER PRIMARY KEY, ad TEXT, sehir TEXT);
    CREATE TABLE siparis(id INTEGER PRIMARY KEY, musteri_id INTEGER, tutar REAL);
    """)
    db.executemany("INSERT INTO musteri VALUES (?,?,?)",
                   [(i, f"Müşteri {i}", rng.choice(["Sakarya", "Antalya", "İstanbul", "Ankara"]))
                    for i in range(1, 801)])
    db.executemany("INSERT INTO siparis VALUES (?,?,?)",
                   [(i, rng.randint(1, 800), round(rng.uniform(10, 900), 2)) for i in range(1, 4001)])
    kayitlar = [f"B{n:08d}" for n in rng.sample(range(10**8), 6000)]
    gelenler = [f"B{n:08d}" for n in rng.sample(range(10**8), 2500)] + rng.sample(kayitlar, 2000)
    ayar = json.dumps({
        "kdv": 0.20, "para_birimi": "TRY",
        "kampanyalar": [{"kod": f"K{i}", "oran": i / 100, "sehirler": ["Sakarya", "Antalya"]} for i in range(80)],
    })
    urunler = [{"ad": f"ürün-{i}", "fiyat": 10 + i % 90, "eposta": f"satici{i}@ornek.com.tr"} for i in range(4000)]
    return {"DB": db, "KAYITLAR": kayitlar, "GELENLER": gelenler, "AYAR_JSON": ayar,
            "URUNLER": urunler, "json": json, "re": re}


SCENARIOS = [
    {
        "id": "n-arti-1",
        "baslik": "Sipariş raporu",
        "kalip": "Döngüde tek tek veritabanı sorgusu (N+1)",
        "ozet": "4.000 siparişin her biri için müşteri ayrı bir sorguyla çekiliyor.",
        "gercek_hayat": "E-ticaret sipariş listeleri, yönetim panelleri",
        "giris": "siparis_raporu",
        "kod": '''\
def siparis_raporu():
    rapor = []
    for sid, mid, tutar in DB.execute("SELECT id, musteri_id, tutar FROM siparis ORDER BY id"):
        ad, sehir = DB.execute("SELECT ad, sehir FROM musteri WHERE id = ?", (mid,)).fetchone()
        rapor.append((sid, ad, sehir, tutar))
    return rapor
''',
    },
    {
        "id": "liste-arama",
        "baslik": "Yoklama kontrolü",
        "kalip": "Döngüde listede arama",
        "ozet": "4.500 öğrenci numarası, 6.000 kayıtlık listede tek tek aranıyor.",
        "gercek_hayat": "Yoklama, stok, kara liste ve yetki kontrolleri",
        "giris": "yoklama_kontrol",
        "kod": '''\
def yoklama_kontrol():
    kayitlilar = list(KAYITLAR)
    return [no for no in GELENLER if no in kayitlilar]
''',
    },
    {
        "id": "tekrar-hesap",
        "baslik": "Rota sayısı",
        "kalip": "Önbelleksiz çift özyineleme",
        "ozet": "Izgarada rota sayan fonksiyon aynı ara sonuçları milyonlarca kez yeniden hesaplıyor.",
        "gercek_hayat": "Rota, fiyat ve öneri hesapları",
        "giris": "rota_raporu",
        "kod": '''\
def rota_sayisi(satir, sutun):
    if satir == 0 or sutun == 0:
        return 1
    return rota_sayisi(satir - 1, sutun) + rota_sayisi(satir, sutun - 1)


def rota_raporu():
    return [rota_sayisi(n, n) for n in range(8, 12)]
''',
    },
    {
        "id": "dongu-isi",
        "baslik": "Fiyat listesi",
        "kalip": "Döngüde değişmeyen işi tekrar yapmak",
        "ozet": "4.000 ürünün her biri için ayar dosyası ve e-posta deseni yeniden hazırlanıyor.",
        "gercek_hayat": "Her istekte ayar okuyan API'ler",
        "giris": "fiyat_listesi",
        "kod": '''\
def fiyat_listesi():
    sonuc = []
    for urun in URUNLER:
        ayar = json.loads(AYAR_JSON)
        desen = re.compile(r"^[\\w.+-]+@[\\w-]+\\.[\\w.]+$")
        if desen.match(urun["eposta"]):
            sonuc.append((urun["ad"], round(urun["fiyat"] * (1 + ayar["kdv"]), 2)))
    return sonuc
''',
    },
]


def get(sid):
    for s in SCENARIOS:
        if s["id"] == sid:
            return s
    raise KeyError(sid)
