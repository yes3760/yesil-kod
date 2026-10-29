def sehir_ortalamasi(df):
    return df.groupby("sehir")["tutar"].mean()
