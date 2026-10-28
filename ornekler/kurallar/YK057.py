def kelime_say(kelimeler):
    sayac = {}
    for k in kelimeler:
        if k in sayac:
            sayac[k] += 1
        else:
            sayac[k] = 1
    return sayac
