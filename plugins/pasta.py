""" Plugin for copypastas

Commands:
    pasta
"""

from random import choice

import discord
import asyncio

from pcbot import Config, Annotate
import plugins

pastas = Config("pastas", data={})


@plugins.command()
def pasta(client: discord.Client, message: discord.Message, name: Annotate.LowerContent):
    """ Use copypastas. Don't forget to enclose the copypasta in quotes: `"pasta goes here"` for multiline
        pasta action. You also need quotes around `<name>` if it has any spaces. """
    # Display a random pasta
    assert not name == ".", choice(list(pastas.data.values()))

    # Pasta might not be in the set
    assert name in pastas.data, "Pasta `{0}` is undefined.".format(name)

    # Display the specified pasta
    yield from client.say(message, pastas.data[name])


@pasta.command()
def add(client: discord.Client, message: discord.Message, name: str.lower, copypasta: Annotate.CleanContent):
    """ Add a pasta with the specified content. """
    assert name not in pastas.data, "Pasta `{0}` already exists. ".format(name)

    # If the pasta doesn't exist, set it
    pastas.data[name] = copypasta
    pastas.save()
    yield from client.say(message, "Pasta `{0}` set.".format(name))


@pasta.command()
def remove(client: discord.Client, message: discord.Message, name: Annotate.LowerContent):
    """ Remove a pasta with the specified name. """
    assert name in pastas.data, "No pasta with name `{0}`.".format(name)

    copypasta = pastas.data.pop(name)
    pastas.save()
    yield from client.say(message, "Pasta `{0}` removed. In case this was a mistake, "
                                   "here's the pasta: ```{1}```".format(name, copypasta))


@plugins.event()
def on_message(client: discord.Client, message: discord.Message):
    """ Use shorthand |<pasta ...> for displaying pastas and remove the user's message. """
    if message.content.startswith("|"):
        asyncio.async(client.delete_message(message))
        yield from pasta(client, message, message.content[1:].lower())

        return True
