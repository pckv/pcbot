""" Script for built-in commands.

This script works just like any of the plugins in plugins/
"""

import random
import logging
from time import time

import discord
import asyncio

from pcbot import utils, Config, Annotate
import plugins


lambdas = Config("lambdas", data={})
lambda_blacklist = []


@plugins.command(name="help", usage="[command]")
def help_(client: discord.Client, message: discord.Message, command: str.lower=None):
    """ Display commands or their usage and description. """
    if command:  # Display this section when a command is passed
        usage, desc = "", ""

        for plugin in plugins.all_values():
            command = utils.get_command(plugin, command)

            if not command:
                continue

            usage = command.usage
            desc = command.description

            # Notify the user when a command is owner specific
            if getattr(command.function, "__owner__", False):
                desc += "\n:information_source:`Only the bot owner can execute this command.`"

        if usage:
            m = "**Usage**: ```{}```**Description**: {}".format(usage, desc)
        else:
            m = "Command `{}` does not exist.".format(command)

        yield from client.send_message(message.channel, m)
        return

    # Display this section when no arguments are passed
    m = "**Commands:**```"

    for plugin in plugins.all_values():
        if getattr(plugin, "__commands", False):  # Massive pile of shit that works (so sorry)
            m += "\n" + "\n".join(sorted(
                cmd.usage for cmd in plugin.__commands
                if not cmd.hidden and
                (not getattr(getattr(cmd, "function"), "__owner__", False) or
                 utils.is_owner(message.author))))

    m += "```\nUse `!help <command>` for command specific help."
    yield from client.send_message(message.channel, m)


@plugins.command(hidden=True)
def setowner(client: discord.Client, message: discord.Message):
    """ Set the bot owner. Only works in private messages. """
    if not message.channel.is_private:
        return

    if utils.owner_cfg.data:
        yield from client.send_message(message.channel, "An owner is already set.")
        return

    owner_code = str(random.randint(100, 999))
    logging.critical("Owner code for assignment: {}".format(owner_code))

    yield from client.send_message(message.channel,
                                   "A code has been printed in the console for you to repeat within 60 seconds.")
    user_code = yield from client.wait_for_message(timeout=60, channel=message.channel, content=owner_code)

    if user_code:
        yield from client.send_message(message.channel, "You have been assigned bot owner.")
        utils.owner_cfg.data = message.author.id
        utils.owner_cfg.save()
    else:
        yield from client.send_message(message.channel, "You failed to send the desired code.")


@plugins.command()
@utils.owner
def stop(client: discord.Client, message: discord.Message):
    """ Stops the bot. """
    yield from client.send_message(message.channel, ":boom: :gun:")
    yield from plugins.save_plugins()
    yield from client.logout()


@plugins.command(usage="[name ...]")
@utils.owner
def game(client: discord.Client, message: discord.Message, name: Annotate.Content=""):
    """ Stop playing or set game to `game`. """
    if name:
        m = "*Set the game to* **{}**.".format(name)
    else:
        m = "*No longer playing.*"

    yield from client.change_status(discord.Game(name=name))
    yield from client.send_message(message.channel, m)


@plugins.command(usage="<python code ...>")
@utils.owner
def do(client: discord.Client, message: discord.Message, script: Annotate.Code):
    """ Execute python code. Coroutines do not work, although you can run `say(msg, c=message.channel)`
    to send a message, optionally to a channel. Eg: `say("Hello!")`. """
    def say(msg, c=message.channel):
        asyncio.async(client.send_message(c, msg))

    try:
        exec(script, locals(), globals())
    except Exception as e:
        say("```" + utils.format_exception(e) + "```")


@plugins.command(name="eval", usage="<python code ...>")
@utils.owner
def eval_(client: discord.Client, message: discord.Message,
             script: Annotate.Code):
    """ Evaluate a python expression. Can be any python code on one line that returns something. """
    try:
        result = eval(script, globals(), locals())
    except Exception as e:
        result = utils.format_exception(e)

    yield from client.send_message(message.channel, "**Result:** \n```{}\n```".format(result))


@plugins.command(name="plugin", usage="[reload | load | unload] [plugin]")
def plugin_(client: discord.Client, message: discord.Message):
    """ Manage plugins.
    **Owner command unless no argument is specified.** """
    yield from client.send_message(message.channel,
                                   "**Plugins:** ```\n" "{}```".format(",\n".join(plugins.all_keys())))


@plugin_.command()
@utils.owner
def reload(client: discord.Client, message: discord.Message, name: str.lower=None):
    """ Reloads a plugin. """
    if name:
        if plugins.get_plugin(name):
            yield from plugins.save_plugin(name)
            plugins.reload_plugin(name)

            m = "Reloaded plugin `{}`.".format(name)
        else:
            m = "`{}` is not a plugin. See `!plugin`.".format(name)
    else:
        yield from plugins.save_plugins()

        for plugin_name in plugins.all_keys():
            plugins.reload_plugin(plugin_name)

        m = "All plugins reloaded."

    yield from client.send_message(message.channel, m)


@plugin_.command(error="You need to specify the name of the plugin to load.")
@utils.owner
def load(client: discord.Client, message: discord.Message, name: str.lower):
    """ Loads a plugin. """
    if not plugins.get_plugin(name):
        loaded = plugins.load_plugin(name)

        if loaded:
            m = "Plugin `{}` loaded.".format(name)
        else:
            m = "Plugin `{}` could not be loaded.".format(name)
    else:
        m = "Plugin `{}` is already loaded.".format(name)

    yield from client.send_message(message.channel, m)


@plugin_.command(error="You need to specify the name of the plugin to unload.")
@utils.owner
def unload(client: discord.Client, message: discord.Message, name: str.lower):
    """ Unloads a plugin. """
    if plugins.get_plugin(name):
        yield from plugins.save_plugin(name)
        plugins.unload_plugin(name)

        m = "Plugin `{}` unloaded.".format(name)
    else:
        m = "`{}` is not a plugin. See `!plugin`.".format(name)

    yield from client.send_message(message.channel, m)


@plugins.command(name="lambda", usage="[add <trigger> <python code> | [remove | enable | disable | source] <trigger>]")
def lambda_(client: discord.Client, message: discord.Message):
    """ Create commands. See `!help do` for information on how the code works.
    **In addition**, there's the `arg(i, default=0)` function for getting arguments in positions,
    where the default argument is what to return when the argument does not exist.
    **Owner command unless no argument is specified.**"""
    yield from client.send_message(message.channel,
                                   "**Lambdas:** ```\n" "{}```".format("\n".join(lambdas.data.keys())))


@lambda_.command()
@utils.owner
def add(client: discord.Client, message: discord.Message, trigger: str.lower, script: Annotate.Code):
    """ Add a command that runs the specified script. """
    if trigger not in lambdas.data:
        lambdas.data[trigger] = script
        lambdas.save()
        m = "Command `{}` set.".format(trigger)
    else:
        m = "Command `{}` already exists.".format(trigger)

    yield from client.send_message(message.channel, m)


@lambda_.command()
@utils.owner
def remove(client: discord.Client, message: discord.Message, trigger: str.lower):
    """ Remove a command. """
    if trigger in lambdas.data:
        lambdas.data.pop(trigger)
        lambdas.save()
        m = "Command `{}` removed.".format(trigger)
    else:
        m = "Command `{}` does not exist.".format(trigger)

    yield from client.send_message(message.channel, m)


@lambda_.command()
@utils.owner
def enable(client: discord.Client, message: discord.Message, trigger: str.lower):
    """ Enable a command. """
    if trigger in lambda_blacklist:
        lambda_blacklist.remove(trigger)
        lambdas.save()
        m = "Command `{}` enabled.".format(trigger)
    else:
        if trigger in lambdas.data:
            m = "Command `{}` is already enabled.".format(trigger)
        else:
            m = "Command `{}` does not exist.".format(trigger)

    yield from client.send_message(message.channel, m)


@lambda_.command()
@utils.owner
def disable(client: discord.Client, message: discord.Message, trigger: str.lower):
    """ Disable a command. """
    if trigger not in lambda_blacklist:
        lambda_blacklist.append(trigger)
        lambdas.save()
        m = "Command `{}` disabled.".format(trigger)
    else:
        if trigger in lambdas.data:
            m = "Command `{}` is already disabled..".format(trigger)
        else:
            m = "Command `{}` does not exist.".format(trigger)

    yield from client.send_message(message.channel, m)


@lambda_.command()
def source(client: discord.Client, message: discord.Message, trigger: str.lower):
    """ Disable source of a command """
    if trigger in lambdas.data:
        m = "Source for `{}`:\n{}".format(trigger, lambdas.data[trigger])
    else:
        m = "Command `{}` does not exist.".format(trigger)

    yield from client.send_message(message.channel, m)


@plugins.command()
def ping(client: discord.Client, message: discord.Message):
    """ Tracks the time spent parsing the command and sending a message. """
    # Track the time it took to receive a message and send it.
    start_time = time()
    first_message = yield from client.send_message(message.channel, "Ping")
    stop_time = time()

    # Edit our message with the tracked time (in ms)
    time_elapsed = (stop_time - start_time) * 1000
    yield from client.edit_message(first_message,
                                   "Ping `{elapsed:.4f}ms`".format(elapsed=time_elapsed))


@asyncio.coroutine
def on_message(client: discord.Client, message: discord.Message, args: list):
    if args[0] in lambdas.data and args[0] not in lambda_blacklist:
        def say(msg, c=message.channel):
            asyncio.async(client.send_message(c, msg))

        def arg(i, default=0):
            if len(args) > i:
                return args[i]
            else:
                return default

        try:
            exec(lambdas.data[args[0]], locals(), globals())
        except Exception as e:
            if utils.is_owner(message.author):
                say("```" + utils.format_exception(e) + "```")

        return True

    return False
