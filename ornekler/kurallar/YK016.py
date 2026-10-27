def gecersiz_var_mi(kayitlar):
    return any([dogrula(k) is False for k in kayitlar])
