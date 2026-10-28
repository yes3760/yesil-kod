def sayilara_cevir(metinler):
    sonuc = []
    for m in metinler:
        try:
            sonuc.append(int(m))
        except ValueError:
            sonuc.append(0)
    return sonuc
