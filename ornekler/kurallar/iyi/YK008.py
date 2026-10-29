import requests


def fiyatlari_cek(urun_kodlari):
    with requests.Session() as oturum:
        return [oturum.get(f"https://api.ornek.com.tr/fiyat/{kod}", timeout=10).json() for kod in urun_kodlari]
