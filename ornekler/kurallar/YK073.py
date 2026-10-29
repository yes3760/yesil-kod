def dolu_satir_sayisi(yol):
    with open(yol) as f:
        satirlar = f.read().split("\n")
    return sum(1 for s in satirlar if s.strip())
