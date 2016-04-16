""" Script template

Commands are specified by name, with keys usage and desc:
commands = {
    "cmd": {
        "usage": "!cmd <arg>",
        "desc": "Is a command."
    }
}

For on_message(), args is a list of all arguments split with shlex.

Commands: none
"""

from random import randint
from time import sleep

import discord
import asyncio


commands = {
    "decide": {
        "usage": "!decide <args ...>",
        "desc": "Decides between given choices in a fancy manner.\n"
                "<args ...> is any number of choices > 2.\n"
                "**Example:** `!decide Yes No \"In the near future\"`."
    }
}


@asyncio.coroutine
def on_command(client: discord.Client, message: discord.Message, args: list):
    if args[0] == "!decide":
        if len(args) > 13:
            yield from client.send_message(message.channel, "I can't roll that many decisions.")
            return

        if len(args) > 2:
            choices = args[1:]
            rolls = randint(len(choices) * 3, len(choices) * 7)
            sleep_time = 0
            sleep_change = 2 / (rolls / 2)
            m = ""

            # Roll and send
            for i in range(rolls):
                if i > rolls / 2:
                    sleep_time += sleep_change

                # Select next choice
                choice = choices[i % len(choices)]

                if not m:
                    m = yield from client.send_message(message.channel, "`" + choice + "`")
                else:
                    try:
                        m = yield from client.edit_message(m, "`" + choice + "`")
                    except discord.errors.HTTPException:
                        pass

                if sleep_time:
                    sleep(sleep_time)

            yield from client.edit_message(m, "**" + m.content[1:-1] + "**" +
                                           " {}".format(message.author.mention))
        else:
            yield from client.send_message(message.channel, "Please see `!help decide`.")

