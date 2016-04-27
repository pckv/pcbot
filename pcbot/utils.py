from enum import Enum

import discord
import asyncio
import aiohttp


def format_command_func(command: str):
    """ Return a formatted string representing the command function name. """
    return "cmd_" + command


def get_command(plugin, command: str):
    """ Find and return a command from a plugin. """
    # Return None if the bot doesn't have any commands
    if not plugin.commands:
        return None

    # Return None if the specified plugin doesn't have the specified command
    if command not in plugin.commands:
        return None

    # Return None if the plugin has no command function of the specified command
    if not getattr(plugin, format_command_func(command)):
        return None

    return getattr(plugin, format_command_func(command))


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
