def sehir_toplamlari(df, sehirler):
    toplamlar = df.groupby("sehir")["tutar"].sum()
    return {s: toplamlar.get(s, 0) for s in sehirler}
