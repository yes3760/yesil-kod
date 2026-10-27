def siralama_puani(ogrenciler, sinif_listesi):
    sira = list(sinif_listesi)
    return [sira.index(o) for o in ogrenciler]
