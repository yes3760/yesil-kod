def musteri_adlari(db):
    return [r[0] for r in db.execute("SELECT ad FROM musteri")]
