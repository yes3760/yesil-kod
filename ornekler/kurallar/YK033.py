def ogrenci_kaydet(satirlar):
    for s in satirlar:
        Ogrenci.objects.create(ad=s["ad"], numara=s["no"])
