from collections import deque


def kuyrugu_isle(isler):
    kuyruk = deque(isler)
    isler.clear()
    sonuc = []
    while kuyruk:
        sonuc.append(kuyruk.popleft() * 2)
    return sonuc
