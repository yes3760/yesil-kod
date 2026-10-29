def kayitli_olanlar(gelenler, kayitlar):
    kayitli = set(kayitlar)
    return [g for g in gelenler if g in kayitli]
