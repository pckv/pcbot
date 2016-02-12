""" Script for creating user based alias commands

Commands: none
"""

import discord
import asyncio

from pcbot.config import Config

commands = {
    "alias": {
        "usage": "!alias [options] <trigger> <text>\n"
                 "Options:\n"
                 "    -anywhere\n",
        "desc": "Assign an alias command, where trigger is the command in it's entirety: `!cmd` or `>cmd` or `cmd`.\n"
                "Feel free to use spaces in a **trigger** by *enclosing it with quotes*, like so: `\"!my cmd\"`.\n"
                "The **text** parameter can be anything, from a link to a paragraph. *Multiple spaces "
                "requires quotes:* `\"this is my alias command\"`.\n"
                "Using the `-anywhere` option will trigger the alias anywhere in text you write."
    }
}

aliases = Config("user_alias", data={})


@asyncio.coroutine
def on_message(client: discord.Client, message: discord.Message, args: list):
    user_id = message.author.id

    # !alias command
    if args[0] == "!alias":
        if len(args) > 2:
            trigger = args[-2].lower()
            text = args[-1]

            # Allow use of command anywhere in text
            anywhere = False
            if len(args) > 3:
                if args[1] == "-anywhere":
                    anywhere = True

            # Initialize users alias list
            if not aliases.data.get(user_id):
                aliases.data[user_id] = {}

            aliases.data[user_id][trigger] = {
                "text": text,
                "anywhere": anywhere
            }
            aliases.save()

            m = "Alias `{}` set for {}.".format(trigger, message.author.mention)

        else:
            m = "Please see `!help alias`."

        yield from client.send_message(message.channel, m)

    # User alias check
    if aliases.data.get(user_id):
        user_aliases = aliases.data[user_id]
        for name, command in user_aliases.items():
            execute = False

            if command["anywhere"]:
                if name in message.content:
                    execute = True
            else:
                if message.content.startswith(name):
                    execute = True

            if execute:
                yield from client.send_message(message.channel, command["text"])
