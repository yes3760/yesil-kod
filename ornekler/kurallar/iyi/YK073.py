def dolu_satir_sayisi(yol):
    with open(yol) as f:
        return sum(1 for s in f if s.strip())
