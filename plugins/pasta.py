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


@plugins.command(usage="<copypasta | add <name> <pasta ...> | remove <pasta>>")
def pasta(client: discord.Client, message: discord.Message, name: Annotate.LowerContent):
    """ Use copypastas. Don't forget to enclose the copypasta in quotes: `"pasta goes here"` for multiline
        pasta action. You also need quotes around `<name>` if it has any spaces. """
    if name == ".":  # Display a random pasta
        yield from client.say(message, choice(list(pastas.data.values())))
        return

    if name not in pastas.data:  # Pasta is not set
        yield from client.say(message, "Pasta `{0}` is undefined.".format(name))
        return

    yield from client.say(message, pastas.data[name])


@pasta.command()
def add(client: discord.Client, message: discord.Message, name: str.lower, copypasta: Annotate.CleanContent):
    """ Add a pasta. """
    if name in pastas.data:
        yield from client.say(message, "Pasta `{0}` already exists. ".format(name))
        return

    pastas.data[name] = copypasta
    pastas.save()
    yield from client.say(message, "Pasta `{0}` set.".format(name))


@pasta.command()
def remove(client: discord.Client, message: discord.Message, name: str.lower):
    """ Remove a pasta. """
    if name not in pastas.data:
        yield from client.say(message, "No pasta with name `{0}`.".format(name))
        return

    copypasta = pastas.data.pop(name)
    pastas.save()
    yield from client.say(message, "Pasta `{0}` set. In case this was a mistake, "
                                   "here's the pasta: ```{1}```".format(name, copypasta))


@asyncio.coroutine
def on_message(client: discord.Client, message: discord.Message, args: list):
    """ Use shorthand |<pasta ...> for displaying pastas and remove the user's message. """
    if args[0].startswith("|"):
        asyncio.async(client.delete_message(message))
        yield from pasta(client, message, message.content[1:])

        return True

    return False
