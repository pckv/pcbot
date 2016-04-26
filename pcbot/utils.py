from enum import Enum

import asyncio
import aiohttp


class Annotate(Enum):
    """ Command annotation enum. """
    Content = 1  # Return all the content after command and/or arguments


@asyncio.coroutine
def download_file(url, **params):
    """ Download and return a byte-like object of a file.

    :param url: download url as str
    :param params: any additional url parameters. """
    with aiohttp.ClientSession() as session:
        response = yield from session.get(url,
                                          params=params)

        file = yield from response.read() if response.status == 200 else []

    return file
