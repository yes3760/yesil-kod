def sehir_toplamlari(df, sehirler):
    sonuc = {}
    for s in sehirler:
        sonuc[s] = df[df["sehir"] == s]["tutar"].sum()
    return sonuc
