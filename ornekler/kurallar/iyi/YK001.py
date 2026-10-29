def siparis_raporu(db, siparisler):
    kimlikler = sorted({s["musteri_id"] for s in siparisler})
    yer_tutucular = ", ".join("?" * len(kimlikler))
    sorgu = "SELECT id, ad FROM musteri WHERE id IN (" + yer_tutucular + ")"
    adlar = dict(db.execute(sorgu, kimlikler).fetchall())
    return [(s["id"], adlar[s["musteri_id"]]) for s in siparisler]
