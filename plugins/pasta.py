""" Script for copypastas

Commands:
!pasta
"""

from random import choice

import discord
import asyncio

from pcbot import Config, Annotate
import plugins

pastas = Config("pastas", data={})
option_add = lambda s: s.lower() == "add" or None
option_remove = lambda s: s.lower() == "remove" or None


@asyncio.coroutine
def cmd_pasta_display(client: discord.Client, message: discord.Message,
                      name: Annotate.LowerContent):
    """ Display a pasta with the specified name. """
    if name == ".":  # Display a random pasta
        yield from client.send_message(message.channel, choice(list(pastas.data.values())))
        return

    if name not in pastas.data:
        yield from client.send_message(message.channel, "Pasta `{0}` is undefined.".format(name))
        return

    yield from client.send_message(message.channel, pastas.data[name])


@asyncio.coroutine
def cmd_pasta_remove(client: discord.Client, message: discord.Message,
                     _: option_remove, name: str.lower) -> cmd_pasta_display:
    """ Remove a pasta with specified name. """
    # The _ param is an option that is parsed with the option_remove function.
    if name not in pastas.data:
        yield from client.send_message(message.channel,
                                       "No pasta with name `{0}`.".format(name))
        return

    pasta = pastas.data.pop(name)
    pastas.save()
    yield from client.send_message(message.channel, "Pasta `{0}` set. In case this was a mistake, "
                                                    "here's the pasta: ```{1}```".format(name, pasta))


@plugins.command(usage="<copypasta | add <name> <pasta ...> | remove <pasta>>")
@asyncio.coroutine
def cmd_pasta(client: discord.Client, message: discord.Message,
              _: option_add, name: str.lower,
              pasta: Annotate.CleanContent) -> cmd_pasta_remove:
    """ Use copypastas. Don't forget to enclose the copypasta in quotes: `"pasta goes here"` for multiline
    pasta action. You also need quotes around a `pastaname` if it has any spaces."""
    # This function explicitly adds pastas. Maybe this command system was a bad idea...
    # The _ param is an option that is parsed with the option_add function. Therefore, it's not needed.
    if name in pastas.data:
        yield from client.send_message(message.channel, "Pasta `{0}` already exists. ".format(name))
        return

    pastas.data[name] = pasta
    pastas.save()
    yield from client.send_message(message.channel, "Pasta `{0}` set.".format(name))


@asyncio.coroutine
def on_message(client: discord.Client, message: discord.Message, args: list):
    """ Use shorthand |<pasta ...> for displaying pastas and remove the user's message. """
    if args[0].startswith("|"):
        asyncio.async(cmd_pasta_display(client, message, message.content[1:]))
        asyncio.async(client.delete_message(message))
