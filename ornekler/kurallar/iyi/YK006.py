from collections import defaultdict


def eslestir(ogrenciler, dersler):
    ogrencinin = defaultdict(list)
    for d in dersler:
        ogrencinin[d["ogrenci_id"]].append(d["ad"])
    return [(o["ad"], ders) for o in ogrenciler for ders in ogrencinin.get(o["id"], ())]
