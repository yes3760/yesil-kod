from django.db.models import F


def notlari_yukselt(ogrenciler):
    ogrenciler.update(not_ortalamasi=F("not_ortalamasi") + 5)
