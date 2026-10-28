def satirlari_oku(yol):
    with open(yol) as f:
        return f.read().split("\n")
