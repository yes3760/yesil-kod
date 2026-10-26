def eslestir(ogrenciler, dersler):
    eslesme = []
    for o in ogrenciler:
        for d in dersler:
            if d["ogrenci_id"] == o["id"]:
                eslesme.append((o["ad"], d["ad"]))
    return eslesme
