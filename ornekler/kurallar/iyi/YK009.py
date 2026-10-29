from collections import deque


def sirayla_isle(isler):
    kuyruk = deque(isler)
    isler.clear()
    biten = []
    while kuyruk:
        biten.append(kuyruk.popleft())
    return biten
