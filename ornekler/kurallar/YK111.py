def tek_sehir_mi(df):
    return df["sehir"].nunique() == 1
