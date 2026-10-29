def kayitlari_ekle(baglanti, kayitlar):
    with baglanti:
        baglanti.executemany("INSERT INTO log (mesaj) VALUES (?)", [(k,) for k in kayitlar])
