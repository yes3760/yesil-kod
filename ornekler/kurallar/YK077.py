def kdv_ekle(df):
    df["kdvli"] = df["fiyat"].apply(lambda x: x * 1.2)
    return df
