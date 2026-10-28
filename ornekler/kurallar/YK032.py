def fiyat_guncelle(db, urunler):
    for u in urunler:
        db.execute("UPDATE urun SET fiyat = ? WHERE id = ?", (u["fiyat"], u["id"]))
