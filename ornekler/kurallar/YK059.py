def tarihleri_isle(metinler):
    sonuc = []
    for m in metinler:
        from datetime import datetime
        sonuc.append(datetime.fromisoformat(m))
    return sonuc
