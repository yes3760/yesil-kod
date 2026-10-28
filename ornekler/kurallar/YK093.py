import redis


def sepetleri_getir(kullanicilar):
    r = redis.Redis()
    return [r.get(f"sepet:{k}") for k in kullanicilar]
