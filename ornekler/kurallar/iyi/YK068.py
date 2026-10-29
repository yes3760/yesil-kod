import math


def ucgen_yukseklikleri(kenarlar):
    oran = math.sqrt(3) / 2
    return [k * oran for k in kenarlar]
