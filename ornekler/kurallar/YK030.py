import subprocess


def resimleri_kucult(dosyalar):
    for d in dosyalar:
        subprocess.run(["convert", d, "-resize", "50%", "kucuk_" + d])
