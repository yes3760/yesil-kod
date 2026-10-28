def aktif_kullanici_sayisi():
    return len(Kullanici.objects.filter(aktif=True))
