def ciftleri_topla(sayilar):
    sonuc = []
    for s in sayilar:
        if s % 2 == 0:
            sonuc = sonuc + [s]
    return sonuc
