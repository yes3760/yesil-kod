import os


def guvenli_yaz(f, kayitlar):
    f.writelines(kayitlar)
    f.flush()
    os.fsync(f.fileno())
