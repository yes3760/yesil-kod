import requests


def fiyatlari_cek(urun_kodlari):
    return [requests.get(f"https://api.ornek.com.tr/fiyat/{kod}").json() for kod in urun_kodlari]
