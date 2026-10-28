import pandas as pd


def tablo_olustur(satirlar):
    df = pd.DataFrame(columns=["ad", "puan"])
    for s in satirlar:
        df.loc[len(df)] = [s["ad"], s["puan"]]
    return df
