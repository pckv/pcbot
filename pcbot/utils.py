from enum import Enum
from functools import wraps

import discord
import asyncio
import aiohttp


def format_command_func(command: str):
    """ Return a formatted string representing the command function name. """
    return "cmd_" + command


def get_command(plugin, command: str):
    """ Find and return a command function from a plugin. """
    if not plugin.commands:  # Return None if the bot doesn't have any commands
        return None

    if command not in plugin.commands:  # Return None if the specified plugin doesn't have the specified command
        return None

    command = format_command_func(command)

    # Return the found command or None if plugin doesn't have the function
    return getattr(plugin, command, None)


class Annotate(Enum):
    """ Command annotation enum. """
    Content = 1  # Return all the content after command and/or arguments


def owner(f):
    """ Decorator that runs the command only if the author is an owner. """
    @wraps(f)
    @asyncio.coroutine
    def decorator(client: discord.Client, message: discord.Message, *args, **kwargs):
        if client.is_owner(message.author):
            yield from f(client, message, *args, **kwargs)

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
