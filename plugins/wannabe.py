""" This plugin is a wannabe script

Commands:
!want
"""

import discord

from pcbot import Annotate
import plugins


@plugins.command(usage="<pasta ...> | [add <name> <pasta ...> | remove <name>]")
def pasta(client: discord.Client, message: discord.Message,
          name: Annotate.LowerContent):
    """ Shows a pasta.
    It is really nice."""
    yield from client.send_message(message.channel, name)


@pasta.command()
def add(client: discord.Client, message: discord.Message,
        name: str.lower, content: Annotate.Content):
    yield from client.send_message(message.channel, "Adding " + name + ":\n```" + content + "```")


@pasta.command()
def remove(client: discord.Client, message: discord.Message,
           name: Annotate.LowerContent):
    yield from client.send_message(message.channel, "Removing " + name)


@pasta.command(name="help")
def help_(client: discord.Client, message: discord.Message):
    yield from client.send_message(message.channel, "No such pasta.")


@help_.command()
def crumbs(client: discord.Client, message: discord.Message, name: str.capitalize):
    yield from client.send_message(message.channel, "Crumbs is a legendary creature, " + name + "!")
