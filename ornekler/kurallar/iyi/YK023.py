def buyuk_siparisler(db):
    return db.execute("SELECT id, tutar FROM siparis WHERE tutar > ?", (500,)).fetchall()
