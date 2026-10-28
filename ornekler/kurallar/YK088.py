def siniflandir(model, ornekler):
    return [model.predict([x])[0] for x in ornekler]
