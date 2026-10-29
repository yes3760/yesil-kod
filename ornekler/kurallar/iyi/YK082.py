def indirim_uygula(df, satir):
    df.loc[satir, "fiyat"] = df.loc[satir, "fiyat"] * 0.9
    return df
