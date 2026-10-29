def raporlar(sablon, ogrenciler):
    return [{**sablon, "ad": o} for o in ogrenciler]
