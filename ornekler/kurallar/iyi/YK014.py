import sqlite3


def kayitlari_yaz(kayitlar):
    baglanti = sqlite3.connect("veri.db")
    with baglanti:
        baglanti.executemany("INSERT INTO log VALUES (?)", [(k,) for k in kayitlar])
    baglanti.close()
