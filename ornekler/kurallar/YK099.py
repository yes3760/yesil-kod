import os


def guvenli_yaz(f, kayitlar):
    for k in kayitlar:
        f.write(k)
        os.fsync(f.fileno())
