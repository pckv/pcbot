""" Script for web commands

Commands:
!define
"""

import requests

import discord
import asyncio

commands = {
    "define": {
        "usage": "!define <query ...>",
        "desc": "Defines a word using Urban Dictionary."
    }
}


@asyncio.coroutine
def on_message(client: discord.Client, message: discord.Message, args: list):
    if args[0] == "!define":
        m = ""
        if len(args) > 1:
            request_params = {"term": " ".join(args[1:])}
            definitions_request = requests.get("http://api.urbandictionary.com/v0/define", request_params)
            definitions = definitions_request.json().get("list")

            if definitions:
                for definition in definitions:
                    if definition.get("example"):
                        definition["example"] = "```{}```".format(definition["example"])

                    m = "**{0}**:\n{1}\n{2}".format(
                        definition["word"],
                        definition["definition"],
                        definition["example"]
                    )

                    if len(m) <= 2000:
                        break

                if len(m) > 2000:
                    m = "Defining this word would be a bad idea."

            else:
                m = "No such word is defined."
        else:
            m = "Please see `!help define`."

        yield from client.send_message(message.channel, m)
