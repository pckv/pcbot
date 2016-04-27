import logging
import re
import importlib
import inspect
from os import listdir, mkdir, path, remove
from getpass import getpass
from argparse import ArgumentParser
from shlex import split as splitargs

import discord
import asyncio

from pcbot.config import Config
from pcbot import utils


# Add all command-line arguments
parser = ArgumentParser(description="Run PCBOT.")
parser.add_argument("--version", help="Return the current version (placebo command; only tells you to git status).",
                    action="version", version="Try: git status")
parser.add_argument("--token", "-t", help="The token to login with. Prompts if omitted.")
parser.add_argument("--email", "-e", help="The email to login to. Token prompt is default.")
parser.add_argument("--new-pass", "-n", help="Always prompts for password.", action="store_true")
parser.add_argument("--log-level", "-l", help="Use the specified logging level (see the docs on logging for values).",
                    type=lambda s: getattr(logging, s.upper()), default=logging.INFO)
start_args = parser.parse_args()

# Setup logger with level specified in start_args or logging.INFO
logging.basicConfig(level=start_args.log_level, format="%(levelname)s [%(module)s] %(asctime)s: %(message)s")


class Bot(discord.Client):
    command_prefix = "!"

    """ The bot, really. """
    def __init__(self):
        super().__init__()
        self.plugins = {}
        self.owner = Config("owner")
        self.autosave_interval = 60 * 30

        self.load_plugin("builtin", "pcbot")  # Load plugin for builtin commands
        self.load_plugins()  # Load all plugins in plugins/

    def load_plugin(self, plugin_name: str, module: str = "plugins"):
        """ Load a plugin with the name plugin_name. This plugin has to be
        situated under plugins/

        Any loaded plugin is imported and stored in the self.plugins dictionary. """
        if not plugin_name.startswith("__") or not plugin_name.endswith("__"):
            try:
                plugin = importlib.import_module("{module}.{plugin}".format(plugin=plugin_name, module=module))
            except ImportError as e:
                logging.warn("COULD NOT LOAD PLUGIN " + plugin_name + "\nReason: " + str(e))
                return False

            self.plugins[plugin_name] = plugin
            logging.debug("LOADED PLUGIN " + plugin_name)
            return True

        return False

    def reload_plugin(self, plugin_name: str):
        """ Reload a plugin. """
        if self.plugins.get(plugin_name):
            self.plugins[plugin_name] = importlib.reload(self.plugins[plugin_name])
            logging.debug("RELOADED PLUGIN " + plugin_name)

    def unload_plugin(self, plugin_name: str):
        """ Unload a plugin by removing it from the plugin dictionary. """
        if self.plugins.get(plugin_name):
            self.plugins.pop(plugin_name)
            logging.debug("UNLOADED PLUGIN " + plugin_name)

    def load_plugins(self):
        """ Perform load_plugin(plugin_name) on all plugins in plugins/ """
        if not path.exists("plugins/"):
            mkdir("plugins/")

        for plugin in listdir("plugins/"):
            plugin_name = path.splitext(plugin)[0]
            self.load_plugin(plugin_name)

    def is_owner(self, user):
        """ Return true if user/member is the assigned bot owner. """
        if type(user) is not str:
            user = user.id

        if user == self.owner.data:
            return True

        return False

    @asyncio.coroutine
    def save_plugin(self, plugin):
        """ Save a plugins files if it has a save function. """
        if plugin in self.plugins.values():
            if getattr(plugin, "save"):
                yield from self.plugins[plugin].save(self)

    @asyncio.coroutine
    def save_plugins(self):
        """ Looks for any save function in a plugin and saves.
        Set up for saving on !stop and periodic saving every 30 mins. """
        for name in self.plugins.keys():
            yield from self.save_plugin(name)

    @asyncio.coroutine
    def autosave(self):
        """ Sleep for set time (default 30 minutes) before saving. """
        while not self.is_closed:
            try:
                yield from asyncio.sleep(self.autosave_interval)
                yield from self.save_plugins()
                logging.debug("Plugins saved")
            except Exception as e:
                logging.info("Error: " + str(e))

    @staticmethod
    def log_message(message: discord.Message, prefix: str=""):
        """ Logs a command/message. """
        logging.info("{prefix}@{0.author} -> {0.content}".format(message, prefix=prefix))

    @staticmethod
    def find_member(server: discord.Server, name, steps=3, mention=True):
        """ Find any member by their name or a formatted mention.
        Steps define the depth at which to search. More steps equal
        less accurate checks.

        +--------+------------------+
        |  step  |     function     |
        +--------+------------------+
        |    0   | perform no check |
        |    1   |   name is equal  |
        |    2   | name starts with |
        |    3   |    name is in    |
        +--------+------------------+

        :param server: discord.Server to look through for members.
        :param name: name as a string or mention to find.
        :param steps: int from 0-3 to specify search depth.
        :param mention: check for mentions. """
        member = None

        # Return a member from mention
        found_mention = re.search(r"<@([0-9]+)>", name)
        if found_mention and mention:
            member = server.get_member(found_mention.group(1))

        if not member:
            # Steps to check, higher values equal more fuzzy checks
            checks = [lambda m: m.name.lower() == name.lower(),
                      lambda m: m.name.lower().startswith(name.lower()),
                      lambda m: name.lower() in m.name.lower()]

            for i in range(steps if steps <= len(checks) else len(checks)):
                member = discord.utils.find(checks[i], server.members)

                if member:
                    break

        # Return the found member or None
        return member

    @staticmethod
    def find_channel(server: discord.Server, name, steps=3, mention=True):
        """ Find any channel by its name or a formatted mention.
            Steps define the depth at which to search. More steps equal
            less accurate checks.

            +--------+------------------+
            |  step  |     function     |
            +--------+------------------+
            |    0   | perform no check |
            |    1   |   name is equal  |
            |    2   | name starts with |
            |    3   |    name is in    |
            +--------+------------------+

            :param server: discord.Server to look through for channels.
            :param name: name as a string or mention to find.
            :param steps: int from 0-3 to specify search depth.
            :param mention: check for mentions. """
        channel = None

        # Return a member from mention
        found_mention = re.search(r"<#([0-9]+)>", name)
        if found_mention and mention:
            channel = server.get_channel(found_mention.group(1))

        if not channel:
            # Steps to check, higher values equal more fuzzy checks
            checks = [lambda c: c.name.lower() == name.lower(),
                      lambda c: c.name.lower().startswith(name.lower()),
                      lambda c: name.lower() in c.name.lower()]

            for i in range(steps if steps <= len(checks) else len(checks)):
                channel = discord.utils.find(checks[i], server.channels)

                if channel:
                    break

        # Return the found channel or None
        return channel

    @asyncio.coroutine
    def on_plugin_message(self, function, message: discord.Message, args: list):
        """ Run the given plugin function (either on_message() or on_command()).
        If the function returns True, log the sent message. """
        success = yield from function(self, message, args)

        if success:
            self.log_message(message, prefix="... ")

    @staticmethod
    def _parse_annotation(param, arg, index, message):
        """ Parse annotations and return the command to use.

        index is basically the arg's index in shelx.split(message.content) """
        if param.annotation:  # Any annotation is a function or Annotation enum
            anno = param.annotation

            # Valid enum checks
            if anno is utils.Annotate.Content:
                return message.content.split(maxsplit=index)[-1]
            
            try:  # Try running as a method
                return anno(arg)
            except TypeError:
                raise TypeError("Command parameter annotation must be either pcbot.utils.Annotate or a function")
        
        return arg  # Return if there was no annotation

    def _parse_command_args(self, command, cmd_args, message):
        """ Parse commands from chat and return args and kwargs to pass into the
        command's function. """
        signature = inspect.signature(command)
        args, kwargs = [], {}
        i = -1

        for arg, param in signature.parameters.items():
            i += 1

            if i == 0:  # Param should have a Client annotation
                if param.annotation is not discord.Client:
                    raise Exception("First command parameter must be of type discord.Client")

                continue
            elif i == 1:  # Param should have a Client annotation
                if param.annotation is not discord.Message:
                    raise Exception("Second command parameter must be of type discord.Message")

                continue
            
            # Any argument to fetch
            if i <= len(cmd_args):  # If there is an argument passed
                cmd_arg = cmd_args[i - 1]
            else:
                if param.default is not inspect._empty:
                    args.append(param.default)
                    continue  # Move onwards once we find a default
                else:
                    break  # We're done when there is no default argument and none passed

            if param.kind is param.POSITIONAL_OR_KEYWORD:
                tmp_arg = self._parse_annotation(param, cmd_arg, i - 1, message)

                if tmp_arg:
                    args.append(tmp_arg)
            # TODO: add positional arguments and keyword arguments

        complete = len(args) == len(signature.parameters.items()) - 2

        return args, kwargs, complete

    @asyncio.coroutine
    def _parse_command(self, plugin, cmd, cmd_args, message):
        """ Try finding a command """
        command = utils.get_command(plugin, cmd)
        args, kwargs = [], {}

        while True:
            if command:
                args, kwargs, complete = self._parse_command_args(command, cmd_args, message)

                if not complete:
                    if "return" in command.__annotations__:
                        command = command.__annotations__["return"]
                        continue
                    else:
                        self.log_message(message)  # Log the command
                        yield from self.plugins["builtin"].cmd_help(self, message, cmd)
                        command = None

            break

        return command, args, kwargs

    @asyncio.coroutine
    def on_ready(self):
        """ Create any tasks for plugins' on_ready() coroutine and create task
        for autosaving. """
        logging.info("\nLogged in as\n"
                     "{0.user.name}\n"
                     "{0.user.id}\n".format(self) +
                     "-" * len(self.user.id))

        # Call any on_ready function in plugins
        for name, plugin in self.plugins.items():
            try:
                self.loop.create_task(plugin.on_ready(self))
            except AttributeError:
                pass

        self.loop.create_task(self.autosave())

    @asyncio.coroutine
    def on_message(self, message: discord.Message):
        """ What to do on any message received.

        The bot will handle all commands in plugins and send on_message to plugins using it. """
        if message.author == self.user:
            return

        if not message.content:
            return

        # Split content into arguments by space (surround with quotes for spaces)
        try:
            cmd_args = splitargs(message.content)
        except ValueError:
            cmd_args = message.content.split()

        # Get command name
        cmd = ""

        if cmd_args[0].startswith(self.command_prefix) and len(cmd_args[0]) > 1:
            cmd = cmd_args[0][1:]

        # Handle commands
        for plugin in self.plugins.values():
            if cmd:
                command, args, kwargs = yield from self._parse_command(plugin, cmd, cmd_args, message)

                if command:
                    self.log_message(message)  # Log the command
                    self.loop.create_task(command(self, message, *args, **kwargs))  # Run command

            # Always run the on_message function if it exists
            if getattr(plugin, "on_message", False):
                self.loop.create_task(self.on_plugin_message(plugin.on_message, message, cmd_args))

bot = Bot()

if __name__ == "__main__":
    login = []

    if not start_args.email:
        # Login with the specified token if specified
        token = start_args.token or input("Token: ")

        login = [start_args.token]
    else:
        # Get the email from commandline argument
        email = start_args.email

        password = ""
        cached_path = bot._get_cache_filename(email)  # Get the name of the would-be cached email

        # If the --new-pass command-line argument is specified, remove the cached password.
        # Useful for when you have changed the password.
        if start_args.new_pass:
            if path.exists(cached_path):
                remove(cached_path)

        # Prompt for password if the cached file does not exist (the user has not logged in before or
        # they they entered the --new-pass argument.
        if not path.exists(cached_path):
            password = getpass()

        login = [email, password]

    try:
        bot.run(*login)
    except discord.errors.LoginFailure as e:
        logging.error(e)
