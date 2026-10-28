def rastgele_soru(db):
    return db.execute("SELECT * FROM soru ORDER BY RANDOM() LIMIT 1").fetchone()
