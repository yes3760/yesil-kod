def kayitlari_ekle(baglanti, kayitlar):
    for k in kayitlar:
        baglanti.execute("INSERT INTO log (mesaj) VALUES (?)", (k,))
        baglanti.commit()
