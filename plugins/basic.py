""" Script for basic commands

Commands:
!ping
!cool
!pasta
"""

import random
import logging

from datetime import datetime

import discord
import asyncio


commands = {
    "ping": {
        "usage": "!ping",
        "desc": "Pong"
    },
    "roll": {
        "usage": "!roll [num | phrase]",
        "desc": "Roll a number from 1-100 if no second argument or second argument is not a number.\n"
                "Alternatively rolls *num* times."
    },

}


@asyncio.coroutine
def on_command(client: discord.Client, message: discord.Message, args: list):
    # Basic check
    if args[0] == "!ping":
        start = datetime.now()
        pong = yield from client.send_message(message.channel, "pong")
        end = datetime.now()
        response = (end - start).microseconds / 1000
        yield from client.edit_message(pong, "pong `{}ms`".format(response))

        logging.info("Response time: {}ms".format(response))

    # Roll from 1-100 or more
    elif args[0] == "!roll":
        if len(args) > 1:
            try:
                roll = random.randint(1, int(args[1]))
            except ValueError:
                roll = random.randint(1, 100)
        else:
            roll = random.randint(1, 100)

        yield from client.send_message(message.channel, "{0.mention} rolls {1}".format(message.author, roll))

    # Have the bot reply confused whenever someone mentions it
    if not message.content.startswith("!") and client.user.id in [m.id for m in message.mentions]:
        phrases = ["what", "huh", "sorry", "pardon", "...", "!", "", "EH!", "wat", "excuse me", "really"]
        phrase = random.choice(phrases)
        if random.randint(0, 4) > 0:
            phrase += "?"

        yield from client.send_message(message.channel, phrase)
