def rapor(stok):
    satirlar = []
    for urun in stok:
        satirlar.append(f"{urun}: {stok[urun]}")
    return satirlar
