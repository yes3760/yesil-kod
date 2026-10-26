import json


def fiyatla(urunler, ayar_metni):
    sonuc = []
    for u in urunler:
        ayar = json.loads(ayar_metni)
        sonuc.append(u["fiyat"] * (1 + ayar["kdv"]))
    return sonuc
