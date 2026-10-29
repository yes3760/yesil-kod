import os


def yeni_dosyalar(gorulen):
    mevcut = set(os.listdir("gelen"))
    return [g for g in gorulen if g not in mevcut]
