def sehre_gore(musteriler):
    gruplar = {}
    for m in musteriler:
        if m["sehir"] not in gruplar:
            gruplar[m["sehir"]] = []
        gruplar[m["sehir"]].append(m)
    return gruplar
