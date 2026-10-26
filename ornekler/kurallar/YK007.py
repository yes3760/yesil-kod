def toplam_ciro(satislar):
    toplam = 0
    for _, satir in satislar.iterrows():
        toplam += satir["adet"] * satir["fiyat"]
    return toplam
