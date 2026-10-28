import re


def posta_kodlari(satirlar):
    return [re.search(r"\d{5}", s) for s in satirlar]
