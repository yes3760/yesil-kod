import pandas as pd


def tablo_olustur(satirlar):
    return pd.DataFrame(satirlar, columns=["ad", "puan"])
