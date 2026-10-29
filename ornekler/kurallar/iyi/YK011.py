def en_ucuz_urun(urunler):
    return min(urunler, key=lambda u: u["fiyat"])
