def kuyrugu_isle(isler):
    sonuc = []
    while isler:
        sonuc.append(isler[0] * 2)
        del isler[0]
    return sonuc
