""" Plugin for creating user based alias commands

Commands:
alias
"""

from collections import defaultdict
from difflib import get_close_matches

import discord
import asyncio

from pcbot import Config, Annotate, utils
import plugins
client = plugins.client  # type: discord.Client


alias_desc = \
    "Assign an alias command, where trigger is the command in it's entirety: `{pre}cmd` or `>cmd` or `cmd`.\n" \
    "Feel free to use spaces in a **trigger** by *enclosing it with quotes*, like so: `\"{pre}my cmd\"`.\n\n" \
    "**Options**:\n" \
    "`-anywhere` makes the alias trigger anywhere in a message, and not just the start of a message.\n" \
    "`-case-sensitive` ensures that you *need* to follow the same casing.\n" \
    "`-delete-message` removes the original message. This option can not be mixed with the `-anywhere` option.\n" \

aliases = Config("user_alias", data=defaultdict(str))


@plugins.command(description=alias_desc, pos_check=lambda s: s.startswith("-"))
async def alias(message: discord.Message, *options: str.lower, trigger: str, text: Annotate.Content):
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

    m = "**Alias assigned.** Type `{}`{} to trigger the alias."
    await client.say(message, m.format(trigger, " anywhere in a message" if anywhere else ""))


@alias.command(name="list")
async def list_aliases(message: discord.Message, member: Annotate.Member=Annotate.Self):
    """ List all user's aliases. """
    assert message.author.id in aliases.data, "**{} has no aliases.**".format(member.display_name)

    # The user is registered so they must have aliases and we display them
    format_aliases = ", ".join(aliases.data[message.author.id].keys())
    await client.say(message, "**Aliases for {}:**```\n{}```\n".format(member.display_name, format_aliases))


@alias.command()
async def remove(message: discord.Message, trigger: Annotate.Content):
    """ Remove user alias with the specified trigger. """
    # Check if the trigger is in the would be list (basically checks if trigger is in [] if user is not registered)
    assert trigger in aliases.data.get(message.author.id, []), \
        "**Alias `{}` has never been set. Check `{}`.".format(trigger, list_aliases.cmd.name_prefix)

    # Trigger is an assigned alias, remove it
    aliases.data[message.author.id].pop(trigger)
    aliases.save()
    await client.say(message, "**Alias `{}` removed.**".format(trigger, message.author))


@plugins.event()
async def on_message(message: discord.Message):
    success = False

    # User alias check
    if message.author.id in aliases.data:
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
                        asyncio.ensure_future(client.delete_message(message))

                await client.say(message, "**{0.display_name}**{1}: {2}".format(
                    message.author, mention, command["text"]))

                success = True

    return success
