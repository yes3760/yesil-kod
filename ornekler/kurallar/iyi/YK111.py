def tek_sehir_mi(df):
    sehir = df["sehir"]
    return bool((sehir == sehir.iloc[0]).all())
