""" Script for web commands

Commands:
    define
"""

import discord

from pcbot import Annotate, utils
import plugins


@plugins.command(usage="<query ...>")
def define(client: discord.Client, message: discord.Message, term: Annotate.LowerCleanContent):
    """ Defines a term using Urban Dictionary. """

    json = yield from utils.download_json("http://api.urbandictionary.com/v0/define", term=term)
    definitions = json["list"] if "list" in json else []

    # Send any valid definition (length of message < 2000 characters)
    if not definitions:
        yield from client.say(message, "Could not define `{0}`.".format(term))
        return

    msg = ""

    for definition in definitions:
        # Format example in code if there is one
        if "example" in definition and definition["example"]:
            definition["example"] = "```{0}```".format(definition["example"])

        # Format definition
        msg = "**{0}**:\n{1}\n{2}".format(
            definition["word"],
            definition["definition"],
            definition["example"]
        )

        # If this definition fits in a message, break the loop and send it
        if len(msg) <= 2000:
            break

        # Cancel if the message is too long
        yield from client.say(message, "Defining this word would be a bad idea.")
        return

    yield from client.say(message, msg)
