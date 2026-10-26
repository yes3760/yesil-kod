def siparis_raporu(db, siparisler):
    rapor = []
    for s in siparisler:
        ad = db.execute("SELECT ad FROM musteri WHERE id = ?", (s["musteri_id"],)).fetchone()
        rapor.append((s["id"], ad))
    return rapor
