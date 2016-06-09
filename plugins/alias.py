""" Script for creating user based alias commands

Commands:
!alias
"""

from collections import defaultdict

import discord
import asyncio

from pcbot import Config, Annotate
import plugins

alias_desc = \
    "Assign an alias command, where trigger is the command in it's entirety: `!cmd` or `>cmd` or `cmd`.\n" \
    "Feel free to use spaces in a **trigger** by *enclosing it with quotes*, like so: `\"!my cmd\"`.\n" \
    "The **text** parameter can be anything, from a link to a paragraph. *Multiple spaces " \
    "requires quotes:* `\"this is my alias command\"`.\n" \
    "`-anywhere`: alias triggers anywhere in text you write.\n" \
    "`-case-sensitive` ensures that you *need* to follow the same casing.\n" \
    "`-delete-message` removes the original message. This option can not be mixed with the `-anywhere` option.\n" \
    "`!alias list` lists all of the users set aliases. This only shows their trigger.\n" \
    "`!alias remove <trigger>` removes the specified alias. Keep in mind that specifying trigger here **is** case " \
    "sensitive. Use `!alias list` to find the correct case."

alias_usage = \
    "<[options] <trigger> <text> | list | remove <trigger>>\n" \
    "Options:\n" \
    "    -anywhere <...>\n" \
    "    -case-sensitive <...>\n" \
    "    -delete-message <...>\n"

aliases = Config("user_alias", data=defaultdict(str))


@plugins.command(usage=alias_usage, description=alias_desc, error="BrokeBack", pos_check=lambda s: s.startswith("-"))
def alias(client: discord.Client, message: discord.Message, *options: str.lower, trigger: str, text: Annotate.Content):
    """ Assign an alias. Description is defined in alias_desc. """
    anywhere = "-anywhere" in options
    case_sensitive = "-case-sensitive" in options
    delete_message = not anywhere and "-delete-message" in options

    # Set options
    aliases.data[message.author.id][trigger if case_sensitive else trigger.lower()] = dict(
        text=text,
        anywhere=anywhere,
        case_sensitive=case_sensitive,
        delete_message=delete_message
    )
    aliases.save()

    yield from client.say(message, "Alias `{0}` set for **{1.name}**.".format(trigger, message.author))


@alias.command(name="list")
def list_(client: discord.Client, message: discord.Message):
    """ List all user's aliases. """
    # List aliases if user has any
    if message.author.id in aliases.data:
        format_aliases = ", ".join(aliases.data[message.author.id].keys())
        yield from client.say(message, "**Aliases for {0.name}:**```{1}```\n".format(message.author, format_aliases))
        return

    # User has no aliases
    yield from client.say(message, "No aliases registered for **{0.name}**.".format(message.author))


@alias.command()
def remove(client: discord.Client, message: discord.Message, trigger: str):
    """ Remove user's alias. """
    # Trigger is an assigned alias, remove it
    if trigger in aliases.data.get(message.author.id, []):
        aliases.data[message.author.id].pop(trigger)
        aliases.save()

        yield from client.say(message, "Removed alias `{0}` for **{1.name}**.".format(trigger, message.author))
        return

    # User has no such alias
    yield from client.say(message, "No alias `{0}` registered for **{1.name}**.".format(trigger, message.author))


@asyncio.coroutine
def on_message(client: discord.Client, message: discord.Message, args: list):
    # User alias check
    if message.author.id in aliases.data:
        success = False
        user_aliases = aliases.data[message.author.id]

        # Check any aliases
        for name, command in user_aliases.items():
            execute = False
            msg = message.content

            if not command.get("case_sensitive", False):
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
                if command.get("delete_message", False):
                    if message.server.me.permissions_in(message.channel).manage_messages:
                        asyncio.async(client.delete_message(message))

                yield from client.say(message, "{0.mention}{1}: {2}".format(message.author, mention, command["text"]))

                success = True

        return success

    # See if the user spelled definitely wrong
    for spelling in ["definately", "definatly", "definantly", "definetly", "definently", "defiantly"]:
        if spelling in message.clean_content:
            yield from client.send_message(message.channel,
                                           "{} http://www.d-e-f-i-n-i-t-e-l-y.com/".format(message.author.mention))
            return True

    return False
