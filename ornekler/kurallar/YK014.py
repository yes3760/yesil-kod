import sqlite3


def kayitlari_yaz(kayitlar):
    for k in kayitlar:
        baglanti = sqlite3.connect("veri.db")
        baglanti.execute("INSERT INTO log VALUES (?)", (k,))
        baglanti.commit()
        baglanti.close()
