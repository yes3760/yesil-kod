def fiyat_guncelle(db, urunler):
    db.executemany("UPDATE urun SET fiyat = ? WHERE id = ?", [(u["fiyat"], u["id"]) for u in urunler])
