import requests


def kur_getir():
    return requests.get("https://api.ornek.com/kur", timeout=10).json()
