""" Script for basic commands

Commands:
!ping
!cool
!pasta
"""

import random

import discord
import asyncio

from pcbot.config import Config

commands = {
    "ping": {
        "usage": "!ping",
        "desc": "Pong"
    },
    "cool": {
        "usage": "!cool",
        "desc": "Inform the bot. Perhaps he really is cool?"
    },
    "pasta": {
        "usage": "!pasta <copypasta | action>\n"
                 "Actions:\n"
                 "    --add <pastaname> <pasta>\n"
                 "    --remove <pastaname>",
        "desc": "Use copypastas. Don't forget to enclose the copypasta in quotes: `\"pasta goes here\"` for multiline"
                "pasta action."
    }
}

pastas = Config("pastas", data={})


@asyncio.coroutine
def on_message(client: discord.Client, message: discord.Message, args: list):
    # Basic check
    if args[0] == "!ping":
        yield from client.send_message(message.channel, "pong")

    # Is the bot cool?
    elif args[0] == "!cool":
        yield from client.send_message(message.channel, "Do you think I'm cool? (reply yes, no or maybe)")
        reply = yield from client.wait_for_message(timeout=30, author=message.author, channel=message.channel)

        if reply:
            if reply.content.lower() == "yes":
                yield from client.send_message(message.channel, "I think you are cool too. :sunglasses:")
            elif reply.content.lower() == "no":
                yield from client.send_message(message.channel, "Well I disagree. :thumbsdown:")
            elif reply.content.lower() == "maybe":
                yield from client.send_message(message.channel, "What kind of answer is that? :zzz:")
            else:
                yield from client.send_message(message.channel, "I don't get it. :frowning:")

    # Copypasta command
    elif args[0] == "!pasta":
        m = ""
        if len(args) > 1:
            # Add a copypasta
            if args[1] == "--add":
                if len(args) > 3:
                    pasta_name = args[2].lower()
                    pasta = args[3]
                    pastas.data[pasta_name] = pasta
                    pastas.save()
                    m = "Pasta `{}` set.".format(pasta_name)
                else:
                    m = "Please follow the format of `!pasta --add <pastaname> <copypasta ...>`"

            # Remove a pasta
            elif args[1] == "--remove":
                if len(args) > 2:
                    pasta_name = args[2].lower()
                    pasta = pastas.data.get(pasta_name)
                    if pasta:
                        pastas.data.pop(pasta_name)
                        pastas.save()
                        m = "Pasta `{}` removed. In case this was a mistake, here's the pasta: ```{}```".format(
                            pasta_name, pasta
                        )
                else:
                    m = "Please specify a pasta to remove. `!pasta --remove <pastaname>`"

            # Retrieve and send pasta
            else:
                if pastas.data:
                    if args[1] == ".":
                        m = random.choice(list(pastas.data.values()))
                    else:
                        m = pastas.data.get(" ".join(args[1:]).lower()) or \
                            "No such pasta is defined. Define with `!pasta --add <pastaname> <copypasta ...>`"
                else:
                    m = "There are no defined pastas. Define with `!pasta --add <pastaname> <copypasta ...>`"

            yield from client.send_message(message.channel, m)

        # No arguments
        else:
            m = "Please see `!help !pasta`."
            yield from client.send_message(message.channel, m)
