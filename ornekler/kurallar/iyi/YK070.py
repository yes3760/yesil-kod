import re

POSTA_KODU = re.compile(r"\d{5}")


def posta_kodlari(satirlar):
    return [POSTA_KODU.search(s) for s in satirlar]
