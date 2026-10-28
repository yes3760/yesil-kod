def ilerleme_mesajlari(adimlar):
    parcalar = []
    mesajlar = []
    for a in adimlar:
        parcalar.append(a)
        mesajlar.append(" > ".join(parcalar))
    return mesajlar
