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

    # Make sure we have something to define
    assert definitions, "Could not define `{}`.".format(term)

    # Send any valid definition (length of message < 2000 characters)
    msg = ""
    for definition in definitions:
        # Format example in code if there is one
        if "example" in definition and definition["example"]:
            definition["example"] = "```{}```".format(definition["example"])

        # Format definition
        msg = "**{}**:\n{}\n{}".format(
            definition["word"],
            definition["definition"],
            definition["example"]
        )

        # If this definition fits in a message, break the loop so that we can send it
        if len(msg) <= 2000:
            break

    # Cancel if the message is too long
    assert len(msg) <= 2000, "Defining this word would be a bad idea."

    # Send the definition
    yield from client.say(message, msg)
