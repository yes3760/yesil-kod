def buyuk_siparisler(db):
    return [s for s in db.execute("SELECT id, tutar FROM siparis").fetchall() if s[1] > 500]
