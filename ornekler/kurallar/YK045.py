def gecersizleri_cikar(kayitlar, gecersizler):
    kalan = list(kayitlar)
    for g in gecersizler:
        kalan.remove(g)
    return kalan
