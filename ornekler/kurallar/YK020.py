def hata_say(log_yolu):
    sayi = 0
    with open(log_yolu) as f:
        for satir in f.readlines():
            if "ERROR" in satir:
                sayi += 1
    return sayi
