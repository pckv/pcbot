""" Script for built-in commands.

This script works just like any of the plugins in plugins/

commands = {

}"""

import re
import random
import logging
import builtins

import discord
import asyncio

from pcbot.utils import Annotate


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
    """ Decorator that runs the command only if the author is an owner. """
    def decorator(client: discord.Client, message: discord.Message, *args, **kwargs):
        if client.is_owner(message.author):
            f(client, message, *args, **kwargs)

    setattr(decorator, "checks_owner", True)
    return decorator


# COMMANDS


@asyncio.coroutine
def help(client: discord.Client, message: discord.Message,
         command: str.lower=None):
    """  """
    # Command specific help
    if command:
        usage, desc = "", ""

        for pl in client.plugins.values():
            # Return if the bot doesn't have any commands
            if not pl.commands:
                return

            # Return if the specified plugin doesn't have the specified command
            if command not in pl.commands:
                return

            if not getattr(pl, command):
                return

            usage = pl.commands["usage"]
            desc = getattr(pl, command).__doc__.strip()

        if usage:
            m = "**Usage**: ```{}```\n" \
                "**Description**: {}".format(usage, desc)
        else:
            m = "Command `{}` does not exist.".format(command)

        yield from client.send_message(message.channel, m)

    # List all commands
    else:
        m = "**Commands:**```"
        for pl in client.plugins.values():
            if pl.commands:
                m += "\n" + "\n".join(pl.commands.keys())

        m += "```\nUse `!help <command>` for command specific help."
        yield from client.send_message(message.channel, m)


@asyncio.coroutine
def setowner(client: discord.Client, message: discord.Message):
    """  """
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
    """  """
    yield from client.send_message(message.channel, ":boom: :gun:")
    yield from client.save_plugins()
    yield from client.logout()


@asyncio.coroutine
@owner
def game(client: discord.Client, message: discord.Message,
         *name: str):
    """  """
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
       code: Annotate.Content):
    """  """
    def say(msg, c=message.channel):
        asyncio.async(client.send_message(c, msg))

    script = get_formatted_code(code)

    try:
        exec(script, locals(), globals())
    except Exception as e:
        say("```" + str(e) + "```")


@asyncio.coroutine
@owner
def eval(client: discord.Client, message: discord.Message,
         code: Annotate.Content):
    """  """
    script = get_formatted_code(code)

    try:
        result = builtins.eval(script, globals(), locals())
    except Exception as e:
        result = str(e)

    yield from client.send_message(message.channel, "**Result:** \n```{}\n```".format(result))


@asyncio.coroutine
@owner
def plugin(client: discord.Client, message: discord.Message,
           option: str, plugin_name: str.lower=""):
    """  """
    if option == "reload":
        if plugin_name:
            if plugin_name in client.plugins:
                yield from client.save_plugin(plugin_name)
                client.reload_plugin(plugin_name)
                
                m = "Reloaded plugin `{}`.".format(plugin_name)
            else:
                m = "`{}` is not a plugin. See `!plugin`.".format(plugin_name)
        else:
            yield from client.save_plugins()

            for pl in client.plugins.keys():
                client.reload_plugin(pl)

            m = "All plugins reloaded."

    elif option == "load":
        if plugin_name:
            if plugin_name not in client.plugins:
                loaded = client.load_plugin(plugin_name)

                if loaded:
                    m = "Plugin `{}` loaded.".format(plugin_name)
                else:
                    m = "Plugin `{}` could not be loaded.".format(plugin_name)
            else:
                m = "Plugin `{}` is already loaded.".format(plugin_name)
        else:
            m = "You need to specify the name of the plugin to load."

    elif option == "unload":
        if plugin_name:
            if plugin_name in client.plugins:
                yield from client.save_plugin(plugin_name)
                client.unload_plugin(plugin_name)

                m = "Plugin `{}` unloaded.".format(plugin_name)
            else:
                m = "`{}` is not a plugin. See `!plugin`.".format(plugin_name)
        else:
            m = "You need to specify the name of the plugin to unload."
    else:
        m = "`{}` is not a valid option.".format(option)

    yield from client.send_message(message.channel, m)


@asyncio.coroutine
def plugin__noargs(client: discord.Client, message: discord.Message):
    """  """
    yield from client.send_message(message.channel,
                                   "**Plugins:** ```\n" "{}```".format(",\n".join(client.plugins.keys())))
