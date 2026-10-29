import queue


def siparis_bekle(siparisler: queue.Queue):
    # Webhook ya da kuyruk: sipariş gelince uyanır, arada işlemci ve ağ boştadır.
    return siparisler.get()
