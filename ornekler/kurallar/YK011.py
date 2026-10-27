def en_ucuz_urun(urunler):
    return sorted(urunler, key=lambda u: u["fiyat"])[0]
