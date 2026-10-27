def yasakli_kelime_var_mi(mesajlar, yasakli_metin):
    sonuc = []
    for m in mesajlar:
        yasaklar = yasakli_metin.lower().split(",")
        sonuc.append(any(y in m for y in yasaklar))
    return sonuc
