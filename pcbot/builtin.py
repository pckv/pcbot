""" Script for built-in commands.

This script works just like any of the plugins in plugins/

commands = {

}"""

import re
import random
import logging

import discord
import asyncio


commands = {
    "help": "!help [command]"
}


def get_formatted_code(code):
    """ Format code from markdown format. This will filter out markdown code
    and give the executable python code, or return a string that would raise
    an error when it's executed by exec() or eval(). """
    match = re.match(r"^(?P<capt>`*)(?:[a-z]+\n)?(?P<code>.+)(?P=capt)$", code, re.DOTALL)

    if match:
        code = match.group("code")

        if not code == "`":
            return code

    return "raise Exception(\"Could not format code.\")"


def owner(f):
    def decorator(client: discord.Client, member: discord.Member, *args, **kwargs):
        if not client.is_owner(member):
            return

        f(client, member, *args, **kwargs)

    return decorator


# COMMANDS


@asyncio.coroutine
def help(client: discord.Client, message: discord.Message,
         command: str.lower=None):
    # Command specific help
    if command:
        usage, desc = "", ""

        for plugin in client.plugins.values():
            # Return if the bot doesn't have any commands
            if not plugin.commands:
                return

            # Return if the specified plugin doesn't have the specified command
            if command not in plugin.commands:
                return

            if not getattr(plugin, command):
                return

            usage = plugin.commands["usage"]
            desc = getattr(plugin, command).__doc__.strip()

        if usage:
            m = "**Usage**: ```{}```\n" \
                "**Description**: {}".format(usage, desc)
        else:
            m = "Command `{}` does not exist.".format(command)

        yield from client.send_message(message.channel, m)

    # List all commands
    else:
        m = "**Commands:**```"
        for plugin in client.plugins.values():
            if plugin.commands:
                m += "\n" + "\n".join(plugin.commands.keys())

        m += "```\nUse `!help <command>` for command specific help."
        yield from client.send_message(message.channel, m)


@asyncio.coroutine
def setowner(client: discord.Client, message: discord.Message):
    if not message.channel.is_private:
        return

    if client.owner.data:
        yield from client.send_message(message.channel, "An owner is already set.")
        return

    owner_code = str(random.randint(100, 999))
    logging.critical("Owner code for assignment: {}".format(owner_code))

    yield from client.send_message(message.channel,
                                   "A code has been printed in the console for you to repeat within 60 seconds.")
    user_code = yield from client.wait_for_message(timeout=60, channel=message.channel, content=owner_code)

    if user_code:
        yield from client.send_message(message.channel, "You have been assigned bot owner.")
        client.owner.data = message.author.id
        client.owner.save()
    else:
        yield from client.send_message(message.channel, "You failed to send the desired code.")


@asyncio.coroutine
@owner
def stop(client: discord.Client, message: discord.Message):
    yield from client.send_message(message.channel, ":boom: :gun:")
    yield from client.save_plugins()
    yield from client.logout()


@asyncio.coroutine
@owner
def game(client: discord.Client, message: discord.Message,
         *name: str):
    if name:
        m = "Set the game to {}.".format(name)
    else:
        m = "No longer playing."

    name = " ".join(name)
    yield from client.change_status(discord.Game(name=name))
    yield from client.send_message(message.channel, m)


@asyncio.coroutine
@owner
def do(client: discord.Client, message: discord.Message,
       *code: str):
