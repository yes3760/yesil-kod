import asyncio


async def tekrar_dene(istek):
    for _ in range(3):
        if await istek():
            return True
        await asyncio.sleep(1)
    return False
