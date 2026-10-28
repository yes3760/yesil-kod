import requests


async def hava_durumu(sehir):
    return requests.get(f"https://api.ornek.com/hava/{sehir}", timeout=5).json()
