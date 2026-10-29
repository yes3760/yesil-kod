def kayitli_eposta(adaylar, kullanicilar):
    epostalar = set(kullanicilar.values())
    return [e for e in adaylar if e in epostalar]
