import pandas as pd


def dosyalari_birlestir(dosya_yollari):
    return pd.concat([pd.read_csv(yol, usecols=["ad", "puan"]) for yol in dosya_yollari])
