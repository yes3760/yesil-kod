def siparis_sayisi(db):
    return len(db.execute("SELECT id FROM siparis").fetchall())
