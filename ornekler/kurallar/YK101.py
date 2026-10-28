import os


def yeni_dosyalar(gorulen):
    yeniler = []
    for g in gorulen:
        if g not in os.listdir("gelen"):
            yeniler.append(g)
    return yeniler
