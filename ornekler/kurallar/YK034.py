def notlari_yukselt(ogrenciler):
    for o in ogrenciler:
        o.not_ortalamasi += 5
        o.save()
