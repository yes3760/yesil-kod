import pandas as pd


def satislari_oku(yol):
    df = pd.read_csv(yol)
    return df["tutar"].sum()
