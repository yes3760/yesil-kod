def ilk_buyuk_siparis(siparisler):
    return next((s for s in siparisler if s["tutar"] > 1000), None)
