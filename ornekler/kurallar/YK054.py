def toplam_puan(puanlar):
    toplam = 0
    for ad, puan in puanlar.items():
        toplam += puan
    return toplam
