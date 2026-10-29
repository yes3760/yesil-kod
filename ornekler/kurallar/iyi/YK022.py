def siparis_sayisi(db):
    return db.execute("SELECT COUNT(*) FROM siparis").fetchone()[0]
