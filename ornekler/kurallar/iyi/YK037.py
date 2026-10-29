import random


def rastgele_soru(db):
    en_kucuk, en_buyuk = db.execute("SELECT MIN(id), MAX(id) FROM soru").fetchone()
    secilen = random.randint(en_kucuk, en_buyuk)
    return db.execute("SELECT id, metin FROM soru WHERE id >= ? ORDER BY id LIMIT 1", (secilen,)).fetchone()
