import pandas as pd


def satislari_oku(yol):
    df = pd.read_csv(yol, usecols=["tutar"], dtype={"tutar": "int64"})
    return df["tutar"].sum()
