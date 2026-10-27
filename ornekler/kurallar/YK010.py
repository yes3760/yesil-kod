def rapor_metni(satirlar):
    metin = ""
    for s in satirlar:
        metin += f"{s['ad']}: {s['tutar']} TL\n"
    return metin
