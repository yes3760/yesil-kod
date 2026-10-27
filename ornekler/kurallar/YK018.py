import pandas as pd


def dosyalari_birlestir(dosya_yollari):
    tablo = pd.DataFrame()
    for yol in dosya_yollari:
        parca = pd.read_csv(yol)
        tablo = pd.concat([tablo, parca])
    return tablo
