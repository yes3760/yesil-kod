import joblib


def tahmin_et(ornekler):
    sonuclar = []
    for x in ornekler:
        model = joblib.load("model.pkl")
        sonuclar.append(model.predict([x])[0])
    return sonuclar
