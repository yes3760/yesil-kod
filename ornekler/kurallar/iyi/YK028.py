def yasakli_kelime_var_mi(mesajlar, yasakli_metin):
    yasaklar = yasakli_metin.lower().split(",")
    return [any(y in m for y in yasaklar) for m in mesajlar]
