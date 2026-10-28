import numpy as np


def notlari_harflendir(notlar):
    harf = np.vectorize(lambda n: "AA" if n >= 90 else "BB")
    return harf(notlar)
