def yoklama(gelenler, kayit):
    kayitlilar = set(kayit)
    return [no for no in gelenler if no in kayitlilar]
