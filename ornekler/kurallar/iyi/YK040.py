def musteri_bul(db, sehir):
    return db.execute("SELECT id, ad FROM musteri WHERE sehir = ?", (sehir,)).fetchall()
