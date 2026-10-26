def yoklama(gelenler, kayit):
    kayitlilar = list(kayit)
    return [no for no in gelenler if no in kayitlilar]
