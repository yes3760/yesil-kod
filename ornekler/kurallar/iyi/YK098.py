def kaydet(dosya, satirlar):
    dosya.writelines(s + "\n" for s in satirlar)
