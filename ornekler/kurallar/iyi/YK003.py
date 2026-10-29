import json


def fiyatla(urunler, ayar_metni):
    kdv = json.loads(ayar_metni)["kdv"]
    return [u["fiyat"] * (1 + kdv) for u in urunler]
