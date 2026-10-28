def sehir_ortalamasi(df):
    return df.groupby("sehir").apply(lambda g: g["tutar"].mean())
