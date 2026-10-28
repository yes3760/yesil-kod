def indirim_uygula(df, satir):
    df["fiyat"][satir] = df["fiyat"][satir] * 0.9
    return df
