def egit(model, veri, kayip_fn, optimizer):
    kayiplar = []
    for x, y in veri:
        kayip = kayip_fn(model(x), y)
        kayip.backward()
        optimizer.step()
        kayiplar.append(kayip.item())
    return kayiplar
