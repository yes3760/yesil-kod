def kdv_ekle(df):
    df["kdvli"] = df["fiyat"] * 1.2
    return df
