def kucuk_harf(df):
    df["eposta"] = df["eposta"].apply(lambda x: x.lower())
    return df
