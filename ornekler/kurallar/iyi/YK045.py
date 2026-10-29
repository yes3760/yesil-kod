def gecersizleri_cikar(kayitlar, gecersizler):
    cikarilacak = set(gecersizler)
    return [k for k in kayitlar if k not in cikarilacak]
