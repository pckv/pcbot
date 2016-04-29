import logging
import importlib
import inspect
import os
from time import time
from getpass import getpass
from argparse import ArgumentParser

import discord
import asyncio

from pcbot import utils, Config


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
    """ The bot, really. """
    command_prefix = "!"

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
                logging.warn("COULD NOT LOAD PLUGIN " + plugin_name + "\n" + utils.format_exception(e))
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
        if not os.path.exists("plugins/"):
            os.mkdir("plugins/")

        for plugin in os.listdir("plugins/"):
            plugin_name = os.path.splitext(plugin)[0]
            self.load_plugin(plugin_name)

    def is_owner(self, user):
        """ Return true if user/member is the assigned bot owner. """
        if type(user) is not str:
            user = user.id

        if user == self.owner.data:
            return True

        return False

    @asyncio.coroutine
    def save_plugin(self, plugin_name):
        """ Save a plugin's files if it has a save function. """
        if plugin_name in self.plugins.keys():
            plugin = self.plugins[plugin_name]
            if getattr(plugin, "save", False):
                try:
                    yield from plugin.save(self)
                except Exception as e:
                    logging.error("An error occurred when saving plugin " + plugin_name + "\n" +
                                  utils.format_exception(e))

    @asyncio.coroutine
    def save_plugins(self):
        """ Looks for any save function in a plugin and saves.
        Set up for saving on !stop and periodic saving every 30 minutes. """
        for name in self.plugins.keys():
            yield from self.save_plugin(name)

    @asyncio.coroutine
    def autosave(self):
        """ Sleep for set time (default 30 minutes) before saving. """
        while not self.is_closed:
            yield from asyncio.sleep(self.autosave_interval)
            yield from self.save_plugins()
            logging.debug("Plugins saved")

    @asyncio.coroutine
    def on_plugin_message(self, function, message: discord.Message, args: list):
        """ Run the given plugin function (either on_message() or on_command()).
        If the function returns True, log the sent message. """
        success = yield from function(self, message, args)

        if success:
            utils.log_message(message, prefix="... ")

    @staticmethod
    def _parse_annotation(param, arg, index, message):
        """ Parse annotations and return the command to use.

        index is basically the arg's index in shelx.split(message.content) """
        if param.annotation:  # Any annotation is a function or Annotation enum
            anno = param.annotation

            # Valid enum checks
            if anno is utils.Annotate.Content:
                return utils.split(message.content, maxsplit=index)[-1]
            elif anno is utils.Annotate.CleanContent:
                return utils.split(message.clean_content, maxsplit=index)[-1]
            elif anno is utils.Annotate.Member:  # Checks bot .Member and .User
                return utils.find_member(message.server, arg)
            elif anno is utils.Annotate.Channel:
                return utils.find_channel(message.server, arg)
            
            try:  # Try running as a method
                return anno(arg)
            except TypeError:
                raise TypeError("Command parameter annotation must be either pcbot.utils.Annotate or a function")
            except:  # On error, eg when annotation is int and given argument is str
                return None
        
        return arg  # Return if there was no annotation

    def _parse_command_args(self, command, cmd_args, message):
        """ Parse commands from chat and return args and kwargs to pass into the
        command's function. """
        signature = inspect.signature(command)
        args, kwargs = [], {}
        index = -1
        num_kwargs = sum(1 for param in signature.parameters.values() if param.kind is param.KEYWORD_ONLY)
        has_pos = False
        num_pos_args = 0

        # Parse all arguments
        for arg, param in signature.parameters.items():
            index += 1

            if index == 0:  # Param should have a Client annotation
                if param.annotation is not discord.Client:
                    raise Exception("First command parameter must be of type discord.Client")

                continue
            elif index == 1:  # Param should have a Client annotation
                if param.annotation is not discord.Message:
                    raise Exception("Second command parameter must be of type discord.Message")

                continue

            # Any argument to fetch
            if index <= len(cmd_args):  # If there is an argument passed
                cmd_arg = cmd_args[index - 1]
            else:
                if param.default is not param.empty:
                    if param.kind is param.POSITIONAL_OR_KEYWORD:
                        args.append(param.default)
                    elif param.kind is param.KEYWORD_ONLY:
                        kwargs[arg] = param.default

                    continue  # Move onwards once we find a default
                else:
                    index -= 1  # Decrement index since there was no argument
                    break  # We're done when there is no default argument and none passed

            if param.kind is param.POSITIONAL_OR_KEYWORD:  # Parse the regular argument
                tmp_arg = self._parse_annotation(param, cmd_arg, index - 1, message)

                if tmp_arg:
                    args.append(tmp_arg)
                else:
                    if param.default is not param.empty:
                        args.append(param.default)
                    else:
                        return args, kwargs, False  # Force quit
            elif param.kind is param.KEYWORD_ONLY:  # Parse a regular arg as a kwarg
                tmp_arg = self._parse_annotation(param, cmd_arg, index - 1, message)

                if tmp_arg:
                    kwargs[arg] = tmp_arg
                else:
                    if param.default is not param.empty:
                        kwargs[arg] = param.default
                    else:
                        return args, kwargs, False  # Force quit
            elif param.kind is param.VAR_POSITIONAL:  # Parse all positional arguments
                has_pos = True

                for cmd_arg in cmd_args[index - 1:-num_kwargs]:
                    tmp_arg = self._parse_annotation(param, cmd_arg, index, message)

                    # Add an option if it's not None. Since positional arguments are optional,
                    # it will not matter that we don't pass it.
                    if tmp_arg:
                        args.append(tmp_arg)
                        num_pos_args += 1

                index += (num_pos_args - 1) if num_pos_args else 0  # Update the new index

        # Number of required arguments are: signature variables - client and message
        # If there are no positional arguments, subtract one from the required arguments
        num_args = len(signature.parameters.items()) - 2
        if has_pos:
            num_args -= int(not bool(num_pos_args))

        num_given = index - 1  # Arguments parsed
        complete = (num_given == num_args)
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
                        utils.log_message(message)  # Log the command
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
            if getattr(plugin, "on_ready", False):
                self.loop.create_task(plugin.on_ready(self))

        self.loop.create_task(self.autosave())

    @asyncio.coroutine
    def on_message(self, message: discord.Message):
        """ What to do on any message received.

        The bot will handle all commands in plugins and send on_message to plugins using it. """
        start_time = time()

        if message.author == self.user:
            return

        if not message.content:
            return

        # Split content into arguments by space (surround with quotes for spaces)
        cmd_args = utils.split(message.content)

        # Get command name
        cmd = ""

        if cmd_args[0].startswith(self.command_prefix) and len(cmd_args[0]) > 1:
            cmd = cmd_args[0][1:]

        # Handle commands
        for plugin in self.plugins.values():
            if cmd:
                command, args, kwargs = yield from self._parse_command(plugin, cmd, cmd_args, message)

                if command:
                    utils.log_message(message)  # Log the command
                    self.loop.create_task(command(self, message, *args, **kwargs))  # Run command

                    # Log time spent parsing the command
                    stop_time = time()
                    time_elapsed = (stop_time - start_time) * 1000
                    logging.debug("Time spent parsing comand: {elapsed:.6f}".format(elapsed=time_elapsed))

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
            if os.path.exists(cached_path):
                os.remove(cached_path)

        # Prompt for password if the cached file does not exist (the user has not logged in before or
        # they they entered the --new-pass argument.
        if not os.path.exists(cached_path):
            password = getpass()

        login = [email, password]

    try:
        bot.run(*login)
    except discord.errors.LoginFailure as e:
        logging.error(e)
