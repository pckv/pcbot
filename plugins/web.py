""" Script for web commands

Commands:
!define
"""

import discord
import asyncio
import aiohttp

import bot

commands = {
    "define": {
        "usage": "!define <query ...>",
        "desc": "Defines a word using Urban Dictionary."
    }
}


@asyncio.coroutine
def on_command(client: bot.Bot, message: discord.Message, args: list):
    if args[0] == "!define":
        m = ""
        if len(args) > 1:
            params = {"term": " ".join(args[1:])}

            # Request a JSON object as a list of definitions
            with aiohttp.ClientSession() as session:
                response = yield from session.get("http://api.urbandictionary.com/v0/define", params=params)
                json = yield from response.json()

            definitions = json["list"] if "list" in json else []

            # Send any valid definition (length of message < 2000 characters)
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
