def toplam_ciro(db):
    return db.execute("SELECT SUM(tutar) FROM siparis").fetchone()[0]
