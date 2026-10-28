def tahmin(model, veri, device):
    sonuclar = []
    for x in veri:
        model.to(device)
        sonuclar.append(model(x.to(device)))
    return sonuclar
