def toplam_ciro(db):
    return sum(satir[0] for satir in db.execute("SELECT tutar FROM siparis"))
