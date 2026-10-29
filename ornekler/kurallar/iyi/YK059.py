from datetime import datetime


def tarihleri_isle(metinler):
    return [datetime.fromisoformat(m) for m in metinler]
