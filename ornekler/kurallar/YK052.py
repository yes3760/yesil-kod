def numara_sozlugu(ogrenciler):
    sozluk = {}
    for o in ogrenciler:
        sozluk[o["no"]] = o["ad"]
    return sozluk
