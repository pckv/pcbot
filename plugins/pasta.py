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

    # We don't use spaces in pastas at all
    parsed_name = name.replace(" ", "")

    # Pasta might not be in the set
    assert parsed_name in pastas.data, "Pasta `{0}` is undefined.".format(name)

    # Display the specified pasta
    yield from client.say(message, pastas.data[parsed_name])


@pasta.command()
def add(client: discord.Client, message: discord.Message, name: str.lower, copypasta: Annotate.CleanContent):
    """ Add a pasta with the specified content. """
    # When creating pastas we don't use spaces either!
    parsed_name = name.replace(" ", "")

    assert parsed_name not in pastas.data, "Pasta `{0}` already exists. ".format(name)

    # If the pasta doesn't exist, set it
    pastas.data[parsed_name] = copypasta
    pastas.save()
    yield from client.say(message, "Pasta `{0}` set.".format(name))


@pasta.command()
def remove(client: discord.Client, message: discord.Message, name: Annotate.LowerContent):
    """ Remove a pasta with the specified name. """
    # We don't even use spaces when removing pastas!
    parsed_name = name.replace(" ", "")

    assert parsed_name in pastas.data, "No pasta with name `{0}`.".format(name)

    copypasta = pastas.data.pop(parsed_name)
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
