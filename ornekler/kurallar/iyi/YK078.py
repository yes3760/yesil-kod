def kucuk_harf(df):
    df["eposta"] = df["eposta"].str.lower()
    return df
