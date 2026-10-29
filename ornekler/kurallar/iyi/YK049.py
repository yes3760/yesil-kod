def _sayi(metin):
    try:
        return int(metin)
    except ValueError:
        return 0


def sayilara_cevir(metinler):
    return [_sayi(m) for m in metinler]
