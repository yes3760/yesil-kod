def rapor_metni(satirlar):
    return "".join(f"{s['ad']}: {s['tutar']} TL\n" for s in satirlar)
