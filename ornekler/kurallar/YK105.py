def kaydet(yol, satirlar):
    with open(yol, "w") as f:
        for s in satirlar:
            f.write(s)
