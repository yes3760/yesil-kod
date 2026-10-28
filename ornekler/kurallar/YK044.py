def kayitli_olanlar(gelenler, kayitlar):
    return [g for g in gelenler if g in set(kayitlar)]
