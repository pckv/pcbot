""" Plugin for built-in commands.

This script works just like any of the plugins in plugins/
"""

import random
import logging
from datetime import datetime, timedelta
import importlib

import discord
import asyncio

from pcbot import utils, Config, Annotate, config
import plugins


lambdas = Config("lambdas", data={})
lambda_config = Config("lambda-config", data=dict(imports=[], blacklist=[]))

code_globals = {}


@plugins.command(name="help", aliases="commands")
def help_(client: discord.Client, message: discord.Message, command: str.lower=None, *args):
    """ Display commands or their usage and description. """
    # Display the specific command
    if command:
        if command.startswith(config.command_prefix):
            command = command[len(config.command_prefix):]

        for plugin in plugins.all_values():
            cmd = plugins.get_command(plugin, command)
            if not cmd:
                continue

            # Get the specific command with arguments and send the help
            cmd = plugins.get_sub_command(cmd, args)
            yield from client.say(message, utils.format_help(cmd))
            break

    # Display every command
    else:
        commands = []

        for plugin in plugins.all_values():
            if getattr(plugin, "__commands", False):  # Massive pile of shit that works (so sorry)
                commands.extend(
                    cmd.name_prefix.split()[0] for cmd in plugin.__commands
                    if not cmd.hidden and
                    (not getattr(getattr(cmd, "function"), "__owner__", False) or
                     utils.is_owner(message.author))
                )

        commands = ", ".join(sorted(commands))

        m = "**Commands**:```{0}```Use `{1}help <command>`, `{1}<command> {2}` or " \
            "`{1}<command> {3}` for command specific help.".format(
            commands, config.command_prefix, *config.help_arg)
        yield from client.say(message, m)


@plugins.command(hidden=True)
def setowner(client: discord.Client, message: discord.Message):
    """ Set the bot owner. Only works in private messages. """
    if not message.channel.is_private:
        return

    assert not utils.owner_cfg.data, "An owner is already set."

    owner_code = str(random.randint(100, 999))
    logging.critical("Owner code for assignment: {}".format(owner_code))

    yield from client.say(message,
                                 "A code has been printed in the console for you to repeat within 60 seconds.")
    user_code = yield from client.wait_for_message(timeout=60, channel=message.channel, content=owner_code)

    assert user_code, "You failed to send the desired code."

    if user_code:
        yield from client.say(message, "You have been assigned bot owner.")
        utils.owner_cfg.data = message.author.id
        utils.owner_cfg.save()


@plugins.command()
@utils.owner
def stop(client: discord.Client, message: discord.Message):
    """ Stops the bot. """
    yield from client.say(message, ":boom: :gun:")
    yield from plugins.save_plugins()
    yield from client.logout()


@plugins.command()
@utils.owner
def game(client: discord.Client, message: discord.Message, name: Annotate.Content=None):
    """ Stop playing or set game to `name`. """
    yield from client.change_status(discord.Game(name=name, type=0))

    if name:
        yield from client.say(message, "*Set the game to* **{}**.".format(name))
    else:
        yield from client.say(message, "*No longer playing.*")


@game.command()
@utils.owner
def stream(client: discord.Client, message: discord.Message, url: str, title: Annotate.Content):
    """ Start streaming a game. """
    yield from client.change_status(discord.Game(name=title, url=url, type=1))
    yield from client.say(message, "Started streaming **{}**.".format(title))


@plugins.command()
@utils.owner
def do(client: discord.Client, message: discord.Message, python_code: Annotate.Code):
    """ Execute python code. Coroutines do not work, although you can run `say(msg, c=message.channel)`
        to send a message, optionally to a channel. Eg: `say("Hello!")`. """
    def say(msg, c=message.channel):
        asyncio.async(client.send_message(c, msg))

    code_globals.update(dict(say=say, message=message, client=client))

    try:
        exec(python_code, code_globals)
    except Exception as e:
        say("```" + utils.format_exception(e) + "```")


@plugins.command(name="eval")
@utils.owner
def eval_(client: discord.Client, message: discord.Message, python_code: Annotate.Code):
    """ Evaluate a python expression. Can be any python code on one line that returns something. """
    code_globals.update(dict(message=message, client=client))

    try:
        result = eval(python_code, code_globals)
    except Exception as e:
        result = utils.format_exception(e)

    yield from client.say(message, "**Result:** \n```{}\n```".format(result))


@plugins.command(name="plugin", hidden=True, aliases="pl")
def plugin_(client: discord.Client, message: discord.Message):
    """ Manage plugins.
        **Owner command unless no argument is specified.** """
    yield from client.say(message,
                          "**Plugins:** ```{}```".format(", ".join(plugins.all_keys())))


@plugin_.command(aliases="r")
@utils.owner
def reload(client: discord.Client, message: discord.Message, name: str.lower=None):
    """ Reloads all plugins or the specified plugin. """
    if name:
        assert plugins.get_plugin(name), "`{}` is not a plugin".format(name)

        # The plugin entered is valid so we reload it
        yield from plugins.save_plugin(name)
        plugins.reload_plugin(name)
        yield from client.say(message, "Reloaded plugin `{}`.".format(name))
    else:
        # Reload all plugins
        yield from plugins.save_plugins()

        for plugin_name in plugins.all_keys():
            plugins.reload_plugin(plugin_name)

        yield from client.say(message, "All plugins reloaded.")


@plugin_.command(error="You need to specify the name of the plugin to load.")
@utils.owner
def load(client: discord.Client, message: discord.Message, name: str.lower):
    """ Loads a plugin. """
    assert not plugins.get_plugin(name), "Plugin `{}` is already loaded.".format(name)

    # The plugin isn't loaded so we'll try to load it
    assert plugins.load_plugin(name), "Plugin `{}` could not be loaded.".format(name)

    # The plugin was loaded successfully
    yield from client.say(message, "Plugin `{}` loaded.".format(name))


@plugin_.command(error="You need to specify the name of the plugin to unload.")
@utils.owner
def unload(client: discord.Client, message: discord.Message, name: str.lower):
    """ Unloads a plugin. """
    assert plugins.get_plugin(name), "`{}` is not a loaded plugin.".format(name)

    # The plugin is loaded so we unload it
    yield from plugins.save_plugin(name)
    plugins.unload_plugin(name)
    yield from client.say(message, "Plugin `{}` unloaded.".format(name))


@plugins.command(name="lambda", hidden=True)
def lambda_(client: discord.Client, message: discord.Message):
    """ Create commands. See `{pre}help do` for information on how the code works.

        **In addition**, there's the `arg(i, default=0)` function for getting arguments in positions,
        where the default argument is what to return when the argument does not exist.
        **Owner command unless no argument is specified.**"""
    yield from client.say(message,
                          "**Lambdas:** ```\n" "{}```".format(", ".join(sorted(lambdas.data.keys()))))


@lambda_.command(aliases="a")
@utils.owner
def add(client: discord.Client, message: discord.Message, trigger: str, python_code: Annotate.Code):
    """ Add a command that runs the specified python code. """
    lambdas.data[trigger] = python_code
    lambdas.save()
    yield from client.say(message, "Command `{}` set.".format(trigger))


@lambda_.command(aliases="r")
@utils.owner
def remove(client: discord.Client, message: discord.Message, trigger: str):
    """ Remove a command. """
    assert trigger in lambdas.data, "Command `{}` does not exist.".format(trigger)

    # The command specified exists and we remove it
    del lambdas.data[trigger]
    lambdas.save()
    yield from client.say(message, "Command `{}` removed.".format(trigger))


@lambda_.command()
@utils.owner
def enable(client: discord.Client, message: discord.Message, trigger: str):
    """ Enable a command. """
    # If the specified trigger is in the blacklist, we remove it
    if trigger in lambda_config.data["blacklist"]:
        lambda_config.data["blacklist"].remove(trigger)
        lambda_config.save()
        yield from client.say(message, "Command `{}` enabled.".format(trigger))
    else:
        assert trigger in lambdas.data, "Command `{}` does not exist.".format(trigger)

        # The command exists so surely it must be disabled
        yield from client.say(message, "Command `{}` is already enabled.".format(trigger))


@lambda_.command()
@utils.owner
def disable(client: discord.Client, message: discord.Message, trigger: str):
    """ Disable a command. """
    # If the specified trigger is not in the blacklist, we add it
    if trigger not in lambda_config.data["blacklist"]:
        lambda_config.data["blacklist"].append(trigger)
        lambda_config.save()
        yield from client.say(message, "Command `{}` disabled.".format(trigger))
    else:
        assert trigger in lambdas.data, "Command `{}` does not exist.".format(trigger)

        # The command exists so surely it must be disabled
        yield from client.say(message, "Command `{}` is already disabled.".format(trigger))


def import_module(module: str, attr: str=None):
    """ Remotely import a module or attribute from module into code_globals. """
    try:
        imported = importlib.import_module(module)
    except ImportError:
        e = "Unable to import module {}.".format(module)
        logging.error(e)
        raise ImportError(e)
    else:
        if attr:
            if hasattr(imported, attr):
                code_globals[attr] = getattr(imported, attr)
            else:
                e = "Module {} has no attribute {}.".format(module, attr)
                logging.error(e)
                raise KeyError(e)
        else:
            code_globals[module] = imported


@lambda_.command(name="import")
@utils.owner
def import_(client: discord.Client, message: discord.Message, module: str, attr: str=None):
    """ Import the specified module. Specifying `attr` will act like `from attr import module`. """
    try:
        import_module(module, attr)
    except ImportError:
        yield from client.say(message, "Unable to import `{}`.".format(module))
    except KeyError:
        yield from client.say(message, "Unable to import `{}` from `{}`.".format(attr, module))
    else:
        # There were no errors when importing, so we add the name to our startup imports
        lambda_config.data["imports"].append((module, attr))
        lambda_config.save()
        yield from client.say(message, "Imported and setup `{}` for import.".format(attr or module))


@lambda_.command()
def source(client: discord.Client, message: discord.Message, trigger: str.lower):
    """ Disable source of a command """
    assert trigger in lambdas.data, "Command `{}` does not exist.".format(trigger)

    # The command exists so we display the source
    yield from client.say(message, "Source for `{}`:\n{}".format(trigger, lambdas.data[trigger]))


@plugins.command(hidden=True)
def ping(client: discord.Client, message: discord.Message):
    """ Tracks the time spent parsing the command and sending a message. """
    # Track the time it took to receive a message and send it.
    start_time = datetime.now()
    first_message = yield from client.say(message, "Pong!")
    stop_time = datetime.now()

    # Edit our message with the tracked time (in ms)
    time_elapsed = (stop_time - start_time).microseconds / 1000
    yield from client.edit_message(first_message,
                                   "Pong! `{elapsed:.4f}ms`".format(elapsed=time_elapsed))


@asyncio.coroutine
def get_changelog(num: int):
    """ Get the latest commit messages from PCBOT. """
    since = datetime.utcnow() - timedelta(days=7)
    commits = yield from utils.download_json("https://api.github.com/repos/{}commits".format(config.github_repo),
                                                since=since.strftime("%Y-%m-%dT00:00:00"))
    changelog = []

    # Go through every commit and add "- " in front of the first line and "  " for all other lines
    # Also add dates after each commit
    for commit in commits[:num]:
        commit_message = commit["commit"]["message"]
        commit_date = commit["commit"]["committer"]["date"]

        formatted_commit = []

        for i, line in enumerate(commit_message.split("\n")):
            if not line == "":
                line = ("- " if i == 0 else "  ") + line

            formatted_commit.append(line)

        # Add the date as well as the
        changelog.append("\n".join(formatted_commit) + "\n  " + commit_date.replace("T", " ").replace("Z", ""))

    # Return formatted changelog
    return "```\n{}```".format("\n\n".join(changelog))


@plugins.command(name=config.name.lower())
def bot_info(client: discord.Client, message: discord.Message):
    """ Display basic information. """
    app_info = yield from client.application_info()

    yield from client.say(message, "**{ver}** - **{name}** ```xl\n"
                                   "Owner   : {owner}\n"
                                   "Up      : {up} UTC\n"
                                   "Servers : {servers}```"
                                   "{desc}".format(
        ver=config.version, name=app_info.name,
        repo="https://github.com/{}".format(config.github_repo),
        owner=str(app_info.owner),
        up=client.time_started.strftime("%d-%m-%Y %H:%M:%S"),
        servers=len(client.servers),
        desc=app_info.description
    ))


@bot_info.command(name="changelog")
def changelog_(client: discord.Client, message: discord.Message, num: utils.int_range(f=1)=3):
    """ Get `num` requests from the changelog. Defaults to 3. """
    changelog = yield from get_changelog(num)
    yield from client.say(message, changelog)


def init():
    """ Import any imports for lambdas. """
    # Add essential globals for "do", "eval" and "lambda" commands
    code_globals.update(dict(
        utils=utils,
        datetime=datetime,
        random=random,
        asyncio=asyncio,
        plugins=plugins
    ))

    # Import modules for "do", "eval" and "lambda" commands
    for module, attr in lambda_config.data["imports"]:
        # Remove any already imported modules
        if (attr or module) in code_globals:
            lambda_config.data["imports"].remove([module, attr])
            lambda_config.save()
            continue

        import_module(module, attr)


@plugins.event()
def on_message(client: discord.Client, message: discord.Message):
    """ Perform lambda commands. """
    args = utils.split(message.content)

    # Check if the command is a lambda command and is not disabled (in the blacklist)
    if args[0] in lambdas.data and args[0] not in lambda_config.data["blacklist"]:
        def say(msg, c=message.channel):
            asyncio.async(client.send_message(c, msg))

        def arg(i, default=0):
            if len(args) > i:
                return args[i]
            else:
                return default

        code_globals.update(dict(arg=arg, say=say, args=args, message=message, client=client))

        # Execute the command
        try:
            exec(lambdas.data[args[0]], code_globals)
        except AssertionError as e:  # Send assertion errors to the core module
            raise AssertionError(e)
        except Exception as e:
            if utils.is_owner(message.author):
                say("```" + utils.format_exception(e) + "```")
            else:
                logging.warn("An exception occurred when parsing lambda command:"
                             "\n{}".format(utils.format_exception(e)))

        return True


# Initialize the plugin's modules
init()
