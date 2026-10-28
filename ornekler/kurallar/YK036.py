def ilk_ayar(db):
    return db.execute("SELECT anahtar, deger FROM ayar").fetchone()
