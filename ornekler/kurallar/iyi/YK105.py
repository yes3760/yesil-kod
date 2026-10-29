def kaydet(yol, satirlar):
    with open(yol, "w") as f:
        f.writelines(satirlar)
