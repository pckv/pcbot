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
                 "    -anywhere <...>\n"
                 "    -case-sensitive <...>\n"
                 "    -list\n"
                 "    --remove <trigger>\n",
        "desc": "Assign an alias command, where trigger is the command in it's entirety: `!cmd` or `>cmd` or `cmd`.\n"
                "Feel free to use spaces in a **trigger** by *enclosing it with quotes*, like so: `\"!my cmd\"`.\n"
                "The **text** parameter can be anything, from a link to a paragraph. *Multiple spaces "
                "requires quotes:* `\"this is my alias command\"`.\n"
                "Using the `-anywhere` option will trigger the alias anywhere in text you write.\n"
                "Using the `-case-sensitive` option will ensure that you *need* to follow the same casing.\n"
                "Using `!alias -list` will list all of the users set aliases. This only shows their trigger.\n"
                "**To remove an alias**, use the `--remove` options and exclude the **text**. Keep in mind that using "
                "trigger here **is** case sensitive. Use `!alias -list` to find the correct case."
    }
}

aliases = Config("user_alias", data={})


@asyncio.coroutine
def on_message(client: discord.Client, message: discord.Message, args: list):
    user_id = message.author.id

    # !alias command
    if args[0] == "!alias":
        m = "Please see `!help alias`."
        if len(args) > 2:
            if args[1] == "--remove":
                trigger = args[2]

                if aliases.data.get(user_id):
                    if aliases.data[user_id].get(trigger):
                        aliases.data[user_id].pop(trigger)
                        aliases.save()

                        m = "Removed alias `{}`.".format(trigger)
            else:
                trigger = args[-2]
                text = args[-1]

                # Set options
                anywhere = False
                case_sensitive = False
                if len(args) > 3:
                    options = args[1:-2]
                    if "-anywhere" in options:
                        anywhere = True
                    if "-case-sensitive" in options:
                        case_sensitive = True

                if not case_sensitive:
                    trigger = trigger.lower()

                # Initialize users alias list
                if not aliases.data.get(user_id):
                    aliases.data[user_id] = {}

                aliases.data[user_id][trigger] = {
                    "text": text,
                    "anywhere": anywhere,
                    "case-sensitive": case_sensitive
                }
                aliases.save()

                m = "Alias `{}` set for {}.".format(trigger, message.author.mention)

        else:
            if len(args) > 1:
                if args[1] == "-list":
                    if aliases.data.get(user_id):
                        m = "**Aliases:**```\n" + "\n".join(list(aliases.data[user_id].keys())) + "```"
                    else:
                        m = "You have no aliases. See `!help alias`."

        yield from client.send_message(message.channel, m)
        return

    # User alias check
    if aliases.data.get(user_id):
        user_aliases = aliases.data[user_id]
        for name, command in user_aliases.items():
            execute = False
            msg = message.content

            if not command["case-sensitive"]:
                msg = msg.lower()

            if command["anywhere"]:
                if name in msg:
                    execute = True
            else:
                if msg.startswith(name):
                    execute = True

            if execute:
                yield from client.send_message(message.channel, command["text"])
