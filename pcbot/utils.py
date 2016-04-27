from enum import Enum

import discord
import asyncio
import aiohttp


def command_func_name(command: str):
    """ Return a formatted string representing the command function name. """
    return "cmd_" + command


class Annotate(Enum):
    """ Command annotation enum. """
    Content = 1  # Return all the content after command and/or arguments


def owner(f):
    """ Decorator that runs the command only if the author is an owner. """
    def decorator(client: discord.Client, message: discord.Message, *args, **kwargs):
        if client.is_owner(message.author):
            f(client, message, *args, **kwargs)

    setattr(decorator, "__owner__", True)
    return decorator


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
