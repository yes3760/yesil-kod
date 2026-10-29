import heapq


def en_iyi_uc(puanlar):
    return heapq.nlargest(3, puanlar)
