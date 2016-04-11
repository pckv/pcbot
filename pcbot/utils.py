import asyncio
import aiohttp


@asyncio.coroutine
def download_file(url, **params):
    with aiohttp.ClientSession() as session:
        response = yield from session.get(url,
                                          params=params)

        file = yield from response.read() if response.status == 200 else []

    return file
