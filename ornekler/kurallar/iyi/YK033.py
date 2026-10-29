def ogrenci_kaydet(satirlar):
    Ogrenci.objects.bulk_create([Ogrenci(ad=s["ad"], numara=s["no"]) for s in satirlar])
