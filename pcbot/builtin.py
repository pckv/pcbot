""" Script for built-in commands.

This script works just like any of the plugins in plugins/
"""

import re
import random
import logging

import discord
import asyncio

from pcbot import owner, Annotate, Config, get_command, format_exception


commands = {
    "help": "!help [command]",
    "setowner": None,
    "stop": "!stop",
    "game": "!game <name ...>",
    "do": "!do <python code ...>",
    "eval": "!eval <expression ...>",
    "plugin": "!plugin [reload | load | unload] [plugin]",
    "lambda": "!lambda [add <trigger> <python code> | [remove | enable | disable | source] <trigger>]",
    "ping": "!ping [message]"
}


lambdas = Config("lambdas", data={})
lambda_blacklist = []


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


# COMMANDS


@asyncio.coroutine
def cmd_help_noargs(client: discord.Client, message: discord.Message):
    m = "**Commands:**```"

    for plugin in client.plugins.values():
        if plugin.commands:
            m += "\n" + "\n".join(usage for cmd, usage in plugin.commands.items() if usage and
                                  (not getattr(get_command(plugin, cmd), "__owner__", False) or
                                  client.is_owner(message.author)))

    m += "```\nUse `!help <command>` for command specific help."
    yield from client.send_message(message.channel, m)


@asyncio.coroutine
def cmd_help(client: discord.Client, message: discord.Message,
             command: str.lower) -> cmd_help_noargs:
    """ Display commands or their usage and description. """
    usage, desc = "", ""

    for plugin in client.plugins.values():
        command_func = get_command(plugin, command)

        if not command_func:
            continue

        usage = plugin.commands[command]
        if command_func.__doc__:
            desc = command_func.__doc__.strip()
        else:
            desc = "Undocumented."

        # Notify the user when a command is owner specific
        if getattr(command_func, "__owner__", False):
            desc += "\n**Only the bot owner can execute this command.**"

    if usage:
        m = "**Usage**: ```{}``` **Description**: {}".format(usage, desc)
    else:
        m = "Command `{}` does not exist.".format(command)

    yield from client.send_message(message.channel, m)


@asyncio.coroutine
def cmd_setowner(client: discord.Client, message: discord.Message):
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
def cmd_stop(client: discord.Client, message: discord.Message):
    """  """
    yield from client.send_message(message.channel, ":boom: :gun:")
    yield from client.save_plugins()
    yield from client.logout()


@asyncio.coroutine
@owner
def cmd_game(client: discord.Client, message: discord.Message,
             name: Annotate.Content):
    """  """
    if name:
        m = "Set the game to **{}**.".format(name)
    else:
        m = "No longer playing."

    yield from client.change_status(discord.Game(name=name))
    yield from client.send_message(message.channel, m)


@asyncio.coroutine
@owner
def cmd_do(client: discord.Client, message: discord.Message,
           code: Annotate.Content):
    """  """
    def say(msg, c=message.channel):
        asyncio.async(client.send_message(c, msg))

    script = get_formatted_code(code)

    try:
        exec(script, locals(), globals())
    except Exception as e:
        say("```" + format_exception(e) + "```")


@asyncio.coroutine
@owner
def cmd_eval(client: discord.Client, message: discord.Message,
             code: Annotate.Content):
    """ Evaluate an expression. """
    script = get_formatted_code(code)

    try:
        result = eval(script, globals(), locals())
    except Exception as e:
        result = format_exception(e)

    yield from client.send_message(message.channel, "**Result:** \n```{}\n```".format(result))


@asyncio.coroutine
def cmd_plugin_noargs(client: discord.Client, message: discord.Message):
    yield from client.send_message(message.channel,
                                   "**Plugins:** ```\n" "{}```".format(",\n".join(client.plugins.keys())))


@asyncio.coroutine
@owner
def cmd_plugin(client: discord.Client, message: discord.Message,
               option: str.lower, plugin_name: str.lower="") -> cmd_plugin_noargs:
    """ Manage plugins. """
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

            for plugin in client.plugins.keys():
                client.reload_plugin(plugin)

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
def cmd_lambda_noargs(client: discord.Client, message: discord.Message):
    yield from client.send_message(message.channel,
                                   "**Lambdas:** ```\n" "{}```".format("\n".join(lambdas.data.keys())))


@asyncio.coroutine
@owner
def cmd_lambda(client: discord.Client, message: discord.Message,
               option: str.lower, trigger: str.lower, code: Annotate.Content="") -> cmd_lambda_noargs:
    """  """
    m = "Command `{}` ".format(trigger)

    if option == "add":
        if code:
            script = get_formatted_code(code)

            if trigger not in lambdas.data:
                lambdas.data[trigger] = script
                lambdas.save()
                m += "set."
            else:
                m += "already exists."
        else:
            m = ""
    elif option == "remove":
        if trigger in lambdas.data:
            lambdas.data.pop(trigger)
            lambdas.save()
            m += "removed."
        else:
            m += "does not exist."
    elif option == "enable":
        if trigger in lambda_blacklist:
            lambda_blacklist.remove(trigger)
            lambdas.save()
            m += "enabled."
        else:
            if trigger in lambdas.data:
                m += "is already enabled."
            else:
                m += "does not exist."
    elif option == "disable":
        if trigger not in lambda_blacklist:
            lambda_blacklist.append(trigger)
            lambdas.save()
            m += "disabled."
        else:
            if trigger in lambdas.data:
                m += "is already disabled."
            else:
                m += "does not exist."
    elif option == "source":
        if trigger in lambdas.data:
            m = "Source for {}: \n{}".format(trigger, lambdas.data[trigger])
        else:
            m += "does not exist."
    else:
        m = ""

    yield from client.send_message(message.channel, m)


@asyncio.coroutine
def cmd_ping(client: discord.Client, message: discord.Message,
             *, msg: Annotate.CleanContent="Ping!"):
    """ Pings along with a message. """
    yield from client.send_message(message.channel, msg)


# EVENTS


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
            if client.is_owner(message.author):
                say("```" + format_exception(e) + "```")

        logging.info("@{0.author} -> {0.content}".format(message))
