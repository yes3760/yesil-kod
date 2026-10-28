def degerlendir(model, veri):
    model.eval()
    dogru = 0
    for x, y in veri:
        cikti = model(x)
        dogru += int((cikti.argmax(1) == y).sum())
    return dogru
