import numpy as np


def donustur(noktalar):
    sonuc = []
    for p in noktalar:
        matris = np.array([[0, -1], [1, 0]])
        sonuc.append(matris @ p)
    return sonuc
