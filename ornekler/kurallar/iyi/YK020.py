def hata_say(log_yolu):
    with open(log_yolu) as f:
        return sum(1 for satir in f if "ERROR" in satir)
