import urllib.request


def sayfalari_indir(adresler):
    return [urllib.request.urlopen(a).read() for a in adresler]
