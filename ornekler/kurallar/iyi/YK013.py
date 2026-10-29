def siralama_puani(ogrenciler, sinif_listesi):
    sira = {}
    for i, ad in enumerate(sinif_listesi):
        sira.setdefault(ad, i)
    return [sira[o] for o in ogrenciler]
