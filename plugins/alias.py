""" Script for creating user based alias commands

Commands:
!alias
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
                 "    -delete-message <...>\n"
                 "    -list\n"
                 "    --remove <trigger>\n",
        "desc": "Assign an alias command, where trigger is the command in it's entirety: `!cmd` or `>cmd` or `cmd`.\n"
                "Feel free to use spaces in a **trigger** by *enclosing it with quotes*, like so: `\"!my cmd\"`.\n"
                "The **text** parameter can be anything, from a link to a paragraph. *Multiple spaces "
                "requires quotes:* `\"this is my alias command\"`.\n"
                "`-anywhere`: alias triggers anywhere in text you write.\n"
                "`-case-sensitive` ensures that you *need* to follow the same casing.\n"
                "`-delete-message` removes the original message. This option can not be mixed with the `-anywhere` "
                "option.\n"
                "`!alias -list` lists all of the users set aliases. This only shows their trigger.\n"
                "**To remove an alias**, use the `--remove` option and exclude the **text**. Keep in mind that "
                "specifying trigger here **is** case sensitive. Use `!alias -list` to find the correct case."
    }
}

always_run = True

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

                        m = "Removed alias `{}` for {}.".format(trigger, message.author.mention)
            else:
                trigger = args[-2]
                text = args[-1]

                # Set options
                anywhere = False
                case_sensitive = False
                delete_message = False
                if len(args) > 3:
                    options = args[1:-2]
                    if "-anywhere" in options:
                        anywhere = True
                    if "-case-sensitive" in options:
                        case_sensitive = True
                    if not anywhere and "-delete-message" in options:
                        delete_message = True

                if not case_sensitive:
                    trigger = trigger.lower()

                # Initialize users alias list
                if not aliases.data.get(user_id):
                    aliases.data[user_id] = {}

                aliases.data[user_id][trigger] = {
                    "text": text,
                    "anywhere": anywhere,
                    "case-sensitive": case_sensitive,
                    "delete-message": delete_message
                }
                aliases.save()

                m = "Alias `{}` set for {}.".format(trigger, message.author.mention)

                # Inform the user when delete message might not work. Basically check if the bot has permissions.
                if not message.server.get_member(client.user.id).permissions_in(message.channel).manage_messages and \
                        delete_message:
                    m += "\n**Note:** *`-delete-message` does not work in this channel. The bot requires " \
                         "`Manage Messages` permission to delete messages.*"

        else:
            if len(args) > 1:
                if args[1] == "-list":
                    if aliases.data.get(user_id):
                        m = "**Aliases for {}:**```\n".format(message.author.mention) + \
                            "\n".join(list(aliases.data[user_id].keys())) + "```"
                    else:
                        m = "No aliases registered for {}. See `!help alias`.".format(message.author.mention)

        yield from client.send_message(message.channel, m)
        return

    # User alias check
    if aliases.data.get(user_id):
        user_aliases = aliases.data[user_id]
        for name, command in user_aliases.items():
            execute = False
            msg = message.content

            if not command.get("case-sensitive", False):
                msg = msg.lower()

            if command.get("anywhere", False):
                if name in msg:
                    execute = True
            else:
                if msg.startswith(name):
                    execute = True

            # Add any mentions to the alias
            mention = ""
            if message.mentions:
                mentions = [member.mention for member in message.mentions]
                mention = " =>(" + ", ".join(mentions) + ")"

            if execute:
                if command.get("delete-message", False):
                    asyncio.async(client.delete_message(message))

                asyncio.async(client.send_message(
                    message.channel,
                    "{}{}: {}".format(message.author.mention, mention, command.get("text")))
                )
