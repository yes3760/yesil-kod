def tahmin(model, veri, device):
    model.to(device)
    return [model(x.to(device)) for x in veri]
