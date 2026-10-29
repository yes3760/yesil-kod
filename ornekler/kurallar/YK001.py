def siparis_raporu(db, siparisler):
    rapor = []
    for s in siparisler:
        ad = db.execute("SELECT ad FROM musteri WHERE id = ?", (s["musteri_id"],)).fetchone()[0]
        rapor.append((s["id"], ad))
    return rapor
