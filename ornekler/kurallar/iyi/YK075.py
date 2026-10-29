import pandas as pd


def tabloya_ekle(satirlar):
    return pd.DataFrame(satirlar, columns=["ad", "puan"])
