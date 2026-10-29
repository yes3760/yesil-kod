from itertools import accumulate


def ilerleme_mesajlari(adimlar):
    return list(accumulate(adimlar, lambda once, a: once + " > " + a))
