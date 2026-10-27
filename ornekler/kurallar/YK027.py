import numpy as np


def normalize(dizi):
    sonuc = np.zeros(len(dizi))
    for i in range(len(dizi)):
        sonuc[i] = (dizi[i] - dizi.mean()) / dizi.std()
    return sonuc
