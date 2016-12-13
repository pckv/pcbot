""" Plugin for copypastas

Commands:
    pasta
"""

from random import choice
from difflib import get_close_matches

import discord
import asyncio

from pcbot import Config, Annotate
import plugins
client = plugins.client  # type: discord.Client


pastas = Config("pastas", data={})


@plugins.command(aliases="paste")
async def pasta(message: discord.Message, name: Annotate.LowerContent):
    """ Use copypastas. Don't forget to enclose the copypasta in quotes: `"pasta goes here"` for multiline
        pasta action. You also need quotes around `<name>` if it has any spaces. """
    # Display a random pasta
    assert not name == ".", choice(list(pastas.data.values()))

    # We don't use spaces in pastas at all
    parsed_name = name.replace(" ", "")

    # Pasta might not be in the set
    assert parsed_name in pastas.data, "Pasta `{}` is undefined.\nPerhaps you meant: `{}`?".format(
        name, ", ".join(get_close_matches(parsed_name, pastas.data.keys(), cutoff=0.5)))

    # Display the specified pasta
    await client.say(message, pastas.data[parsed_name])


@pasta.command(aliases="a create set")
async def add(message: discord.Message, name: str.lower, copypasta: Annotate.CleanContent):
    """ Add a pasta with the specified content. """
    # When creating pastas we don't use spaces either!
    parsed_name = name.replace(" ", "")

    assert parsed_name not in pastas.data, "Pasta `{}` already exists. ".format(name)

    # If the pasta doesn't exist, set it
    pastas.data[parsed_name] = copypasta
    pastas.save()
    await client.say(message, "Pasta `{}` set.".format(name))


@pasta.command(aliases="r delete")
async def remove(message: discord.Message, name: Annotate.LowerContent):
    """ Remove a pasta with the specified name. """
    # We don't even use spaces when removing pastas!
    parsed_name = name.replace(" ", "")

    assert parsed_name in pastas.data, "No pasta with name `{}`.".format(name)

    copypasta = pastas.data.pop(parsed_name)
    pastas.save()
    await client.say(message, "Pasta `{}` removed. In case this was a mistake, "
                                   "here's the pasta: ```{}```".format(name, copypasta))


@plugins.event()
async def on_message(message: discord.Message):
    """ Use shorthand |<pasta ...> for displaying pastas and remove the user's message. """
    if message.content.startswith("|"):
        if message.channel.permissions_for(message.server.me).manage_messages:
            asyncio.ensure_future(client.delete_message(message))
        try:
            await pasta(message, message.content[1:].lower())
        except AssertionError as e:
            await client.say(message, e)
        finally:
            return True
