import pandas as pd


def tabloya_ekle(satirlar):
    df = pd.DataFrame(columns=["ad", "puan"])
    for s in satirlar:
        df = df.append(s, ignore_index=True)
    return df
