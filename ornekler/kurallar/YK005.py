import time


def siparis_bekle(api):
    while True:
        if api.yeni_siparis_var_mi():
            return api.siparisi_al()
        time.sleep(0.1)
