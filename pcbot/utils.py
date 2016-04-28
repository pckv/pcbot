from enum import Enum
from functools import wraps
import shlex

import discord
import asyncio
import aiohttp


class Annotate(Enum):
    """ Command annotation enum. """
    Content = 1  # Return all the content after command and/or arguments with Message.content
    CleanContent = 2  # Same as above but uses Message.clean_content


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


def format_exception(e):
    """ Returns a formatted string of Exception: str """
    return type(e).__name__ + ": " + str(e)


def split(string, maxsplit=-1):
    if maxsplit == -1:
        try:
            return shlex.split(string)
        except ValueError:
            return string.split()

    split_object = shlex.shlex(string, posix=True)
    split_object.whitespace_split = True
    split_object.commenters = ""
    maxsplit_object = []
    splits = 0

    while splits < maxsplit:
        maxsplit_object.append(next(split_object))

        splits += 1

    maxsplit_object.append(split_object.instream.read())

    return maxsplit_object
