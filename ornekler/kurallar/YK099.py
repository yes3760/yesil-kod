import os


def guvenli_yaz(f, kayitlar):
    for k in kayitlar:
        f.write(k)
        f.flush()
        os.fsync(f.fileno())
