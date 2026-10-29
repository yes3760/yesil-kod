import json


def kullanici_ayari(varsayilan, tema):
    ayar = json.loads(json.dumps(varsayilan))
    ayar["tema"] = tema
    return ayar
