import redis


def sepetleri_getir(kullanicilar):
    r = redis.Redis()
    return r.mget([f"sepet:{k}" for k in kullanicilar])
