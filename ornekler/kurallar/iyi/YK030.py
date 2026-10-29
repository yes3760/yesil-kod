import subprocess


def resimleri_kucult(dosyalar):
    # Tek süreç bütün dosyaları işler (ya da Pillow ile hiç süreç açmadan).
    subprocess.run(["mogrify", "-resize", "50%", "-path", "kucuk", *dosyalar], check=True)
