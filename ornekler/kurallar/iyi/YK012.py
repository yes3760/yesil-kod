import joblib


def tahmin_et(ornekler):
    model = joblib.load("model.pkl")
    return list(model.predict(ornekler))
