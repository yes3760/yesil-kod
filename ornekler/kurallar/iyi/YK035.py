def aktif_kullanici_sayisi():
    return Kullanici.objects.filter(aktif=True).count()
