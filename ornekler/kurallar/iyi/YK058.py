from collections import defaultdict


def sehre_gore(musteriler):
    gruplar = defaultdict(list)
    for m in musteriler:
        gruplar[m["sehir"]].append(m)
    return dict(gruplar)
