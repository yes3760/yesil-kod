import requests


def sayfalari_indir(adresler):
    with requests.Session() as oturum:
        return [oturum.get(a, timeout=10).content for a in adresler]
