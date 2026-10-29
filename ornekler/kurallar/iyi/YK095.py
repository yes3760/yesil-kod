import httpx


async def hava_durumu(sehir):
    async with httpx.AsyncClient(timeout=5) as istemci:
        yanit = await istemci.get(f"https://api.ornek.com/hava/{sehir}")
        return yanit.json()
