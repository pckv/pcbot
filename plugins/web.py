""" Script for web commands

Commands:
!define
"""

import discord
import aiohttp

from pcbot import Annotate
import plugins


@plugins.command(usage="<query ...>")
def define(client: discord.Client, message: discord.Message, term: Annotate.LowerCleanContent):
    """ Defines a term using Urban Dictionary. """
    params = {"term": term}

    # Request a JSON object as a list of definitions
    with aiohttp.ClientSession() as session:
        response = yield from session.get("http://api.urbandictionary.com/v0/define", params=params)
        json = yield from response.json() if response.status == 200 else []

    definitions = json["list"] if "list" in json else []

    # Send any valid definition (length of message < 2000 characters)
    if not definitions:
        yield from client.say(message, "Could not define `{0}`.".format(term))
        return

    msg = ""

    for definition in definitions:
        # Format example in code if there is one
        if "example" in definition:
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
