def musteri_adlari(db):
    return [r[1] for r in db.execute("SELECT * FROM musteri")]
