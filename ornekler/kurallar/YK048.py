import copy


def raporlar(sablon, ogrenciler):
    sonuc = []
    for o in ogrenciler:
        r = copy.deepcopy(sablon)
        r["ad"] = o
        sonuc.append(r)
    return sonuc
