""" Plugin for creating user based alias commands

Commands:
alias
"""

from collections import defaultdict

import discord
import asyncio

from pcbot import Config, Annotate
import plugins

alias_desc = \
    "Assign an alias command, where trigger is the command in it's entirety: `{pre}cmd` or `>cmd` or `cmd`.\n" \
    "Feel free to use spaces in a **trigger** by *enclosing it with quotes*, like so: `\"{pre}my cmd\"`.\n" \
    "The **text** parameter can be anything, from a link to a paragraph. *Multiple spaces " \
    "requires quotes:* `\"this is my alias command\"`.\n" \
    "`-anywhere`: alias triggers anywhere in text you write.\n" \
    "`-case-sensitive` ensures that you *need* to follow the same casing.\n" \
    "`-delete-message` removes the original message. This option can not be mixed with the `-anywhere` option.\n" \
    "`{pre}alias list` lists all of the users set aliases. This only shows their trigger.\n" \
    "`{pre}alias remove <trigger>` removes the specified alias. Keep in mind that specifying trigger here **is** " \
    "case sensitive. Use `{pre}alias list` to find the correct case."

alias_usage = "<[-anywhere] [-case-sensitive] [-delete-message] <trigger> <text> | list | remove <trigger>>\n"

aliases = Config("user_alias", data=defaultdict(str))


@plugins.command(usage=alias_usage, description=alias_desc, pos_check=lambda s: s.startswith("-"))
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
    assert aliases.data.get(message.author.id, False), "No aliases registered for **{0.name}**.".format(message.author)

    # The user is registered so they must have aliases and we display them
    format_aliases = ", ".join(aliases.data[message.author.id].keys())
    yield from client.say(message, "**Aliases for {0.name}:**```{1}```\n".format(message.author, format_aliases))


@alias.command()
def remove(client: discord.Client, message: discord.Message, trigger: Annotate.Content):
    """ Remove user's alias. """
    # Check if the trigger is in the would be list (basically checks if trigger is in [] if user is not registered)
    assert trigger in aliases.data.get(message.author.id, []), \
        "No alias `{0}` registered for **{1.name}**.".format(trigger, message.author)

    # Trigger is an assigned alias, remove it
    aliases.data[message.author.id].pop(trigger)
    aliases.save()
    yield from client.say(message, "Removed alias `{0}` for **{1.name}**.".format(trigger, message.author))


@plugins.event
def on_message(client: discord.Client, message: discord.Message):
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
                        asyncio.async(client.delete_message(message))

                yield from client.say(message, "**{0.display_name}**{1}: {2}".format(
                    message.author, mention, command["text"]))

                success = True

    # See if the user spelled definitely wrong
    for spelling in ["definately", "definatly", "definantly", "definetly", "definently", "defiantly"]:
        if spelling in message.clean_content:
            yield from client.send_message(message.channel,
                                           "{} http://www.d-e-f-i-n-i-t-e-l-y.com/".format(message.author.mention))
            success = True

    return success
