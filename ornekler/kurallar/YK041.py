def ilk_buyuk_siparis(siparisler):
    return [s for s in siparisler if s["tutar"] > 1000][0]
