import numpy as np


def notlari_harflendir(notlar):
    return np.where(notlar >= 90, "AA", "BB")
