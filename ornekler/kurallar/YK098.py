def kaydet(dosya, satirlar):
    for s in satirlar:
        dosya.write(s + "\n")
        dosya.flush()
