def kayitli_eposta(adaylar, kullanicilar):
    return [e for e in adaylar if e in kullanicilar.values()]
