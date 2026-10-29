import numpy as np

DONDUR = np.array([[0, -1], [1, 0]])


def donustur(noktalar):
    return [DONDUR @ p for p in noktalar]
