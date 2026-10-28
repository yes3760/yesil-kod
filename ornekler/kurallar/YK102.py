import time


def kuyruk_bekle(kuyruk):
    while kuyruk.bos_mu():
        time.sleep(0.001)
    return kuyruk.al()
