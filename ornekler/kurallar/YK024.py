import json


def ayar_kopyasi(ayar):
    return json.loads(json.dumps(ayar))
