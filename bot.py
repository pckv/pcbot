import logging
import random
import re
import importlib
from os import listdir, path, remove
from getpass import getpass
from argparse import ArgumentParser
from shlex import split as splitargs

import discord
import asyncio

from pcbot.config import Config

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
    def __init__(self):
        super().__init__()
        self.plugins = {}
        self.owner = Config("owner")
        self.lambdas = Config("lambdas", data={})
        self.lambda_blacklist = []
        self.autosave_interval = 60 * 30

        self.load_plugins()

    def load_plugin(self, plugin_name: str):
        """ Load a plugin with the name plugin_name. This plugin has to be
        situated under plugins/

        Any loaded plugin is imported and stored in the self.plugins dictionary. """
        if not plugin_name.startswith("__") or not plugin_name.endswith("__"):
            try:
                plugin = importlib.import_module("plugins.{}".format(plugin_name))
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

    def save_plugin(self, plugin):
        """ Save a plugins files if it has a save function. """
        if self.plugins.get(plugin):
            try:
                yield from self.plugins[plugin].save(self)
            except AttributeError:
                pass

    def save_plugins(self):
        """ Looks for any save function in a plugin and saves.
        Set up for saving on !stop and periodic saving every 30 mins. """
        for name, _ in self.plugins.items():
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

        This coroutine has several built-in commands hardcoded. These are
        currently undocumented, and categorized into:

        Universal commands:
           * !help [command]
           * !setowner          Private message only

        Owner only commands:
           * !stop
           * !game <name ...>
           * !do <python code>
           * !eval <python code>
           * !plugin [reload | load | unload] [plugin]
           * !lambda [add <trigger> <python code> | [remove | enable | disable | source] <trigger>]

        The bot then proceeds to run any plugin's on_command() and on_message() function.
        """
        if message.author == self.user:
            return

        if not message.content:
            return

        # Split content into arguments by space (surround with quotes for spaces)
        try:
            args = splitargs(message.content)
        except ValueError:
            args = message.content.split()

        if self.is_owner(message.author):
            # Stops the bot
            if message.content == "!stop":
                yield from self.send_message(message.channel, ":boom: :gun:")
                yield from self.save_plugins()
                yield from self.logout()

            # Sets the bots game
            elif args[0] == "!game":
                if len(args) > 1:
                    game = discord.Game(name=args[1])
                    logging.debug("Setting bot game to {}".format(args[1]))
                    yield from self.change_status(game)
                else:
                    yield from self.send_message(message.channel, "Usage: `!game <game>`")

            # Runs a piece of code
            elif args[0] == "!do":
                if len(args) > 1:
                    def say(msg, c=message.channel):
                        asyncio.async(self.send_message(c, msg))

                    script = self.get_formatted_code(message.content[len("!do "):])

                    print(script)

                    try:
                        exec(script, locals(), globals())
                    except Exception as e:
                        say("```" + str(e) + "```")

            # Evaluates a piece of code and prints the result
            elif args[0] == "!eval":
                if len(args) > 1:
                    script = self.get_formatted_code(message.content[len("!eval "):])

                    try:
                        result = eval(script, globals(), locals())
                    except Exception as e:
                        result = str(e)

                    yield from self.send_message(message.channel, "**Result:** \n```{}\n```".format(result))

            # Plugin specific commands
            elif args[0] == "!plugin":
                if len(args) > 1:
                    if args[1] == "reload":
                        if len(args) > 2:
                            if self.plugins.get(args[2]):
                                yield from self.save_plugin(args[2])
                                self.reload_plugin(args[2])
                                yield from self.send_message(message.channel, "Reloaded plugin `{}`.".format(args[2]))
                            else:
                                yield from self.send_message(message.channel,
                                                             "`{}` is not a plugin. See `!plugin`.".format(args[2]))
                        else:
                            yield from self.save_plugins()
                            for plugin in list(self.plugins.keys()):
                                self.reload_plugin(plugin)
                            yield from self.send_message(message.channel, "All plugins reloaded.")
                    elif args[1] == "load":
                        if len(args) > 2:
                            if not self.plugins.get(args[2].lower()):
                                loaded = self.load_plugin(args[2].lower())
                                if loaded:
                                    yield from self.send_message(message.channel, "Plugin `{}` loaded.".format(args[2]))
                                else:
                                    yield from self.send_message(message.channel,
                                                                 "Plugin `{}` could not be loaded.".format(args[2]))
                            else:
                                yield from self.send_message(message.channel,
                                                             "Plugin `{}` is already loaded.".format(args[2]))
                    elif args[1] == "unload":
                        if len(args) > 2:
                            if self.plugins[args[2].lower()]:
                                yield from self.save_plugin(args[2])
                                self.unload_plugin(args[2].lower())
                                yield from self.send_message(message.channel, "Plugin `{}` unloaded.".format(args[2]))
                            else:
                                yield from self.send_message(message.channel,
                                                             "`{}` is not a plugin. See `!plugin`.".format(args[2]))
                    else:
                        yield from self.send_message(message.channel, "`{}` is not a valid argument.".format(args[1]))
                else:
                    yield from self.send_message(message.channel,
                                                 "**Plugins:** ```\n"
                                                 "{}```".format(",\n".join(self.plugins.keys())))

            elif args[0] == "!lambda":
                m = ""

                if len(args) > 2:
                    name = args[2].lower()
                    m = "Command `{}` ".format(name)

                    if args[1] == "add" and len(args) > 3:
                        # Get the clean representation of the command
                        cmd = self.get_formatted_code(message.content[len(" ".join(args[:3])) + 1:])

                        if name not in self.lambdas.data:
                            self.lambdas.data[name] = cmd
                            self.lambdas.save()
                            m += "set."
                        else:
                            m += "already exists."
                    elif args[1] == "remove":
                        if name in self.lambdas.data:
                            self.lambdas.data.pop(name)
                            self.lambdas.save()
                            m += "removed."
                        else:
                            m += "does not exist."
                    elif args[1] == "disable":
                        if name not in self.lambda_blacklist:
                            self.lambda_blacklist.append(name)
                            self.lambdas.save()
                            m += "disabled."
                        else:
                            if name in self.lambdas.data:
                                m += "is already disabled."
                            else:
                                m += "does not exist."
                    elif args[1] == "enable":
                        if name in self.lambda_blacklist:
                            self.lambda_blacklist.remove(name)
                            self.lambdas.save()
                            m += "enabled."
                        else:
                            if name in self.lambdas.data:
                                m += "is already enabled."
                            else:
                                m += "does not exist."
                    elif args[1] == "source":
                        if name in self.lambdas.data:
                            m = "Source for {}: \n{}".format(name, self.lambdas.data[name])
                        else:
                            m += "does not exist."

                if m:
                    yield from self.send_message(message.channel, m)

            # Originally just a test command
            elif message.content == "!count":
                if not self.message_count.data.get(message.channel.id):
                    self.message_count.data[message.channel.id] = 0

                self.message_count.data[message.channel.id] += 1
                yield from self.send_message(message.channel, "I have counted `{}` times in this channel.".format(
                    self.message_count.data[message.channel.id]
                ))
                self.message_count.save()

        # Run plugins on_message
        for name, plugin in self.plugins.items():
            # Try running the command function in this plugin if a command matches
            if args[0][1:] in plugin.commands:
                if getattr(plugin, "on_command", False):
                    self.log_message(message)
                    yield from plugin.on_command(self, message, args)

            # Always run the on_message function if it exists
            if getattr(plugin, "on_message", False):
                self.loop.create_task(self.on_plugin_message(plugin.on_message, message, args))

        if args[0] in self.lambdas.data and args[0] not in self.lambda_blacklist:
            def say(msg, c=message.channel):
                asyncio.async(self.send_message(c, msg))

            def arg(i, default=0):
                if len(args) > i:
                    return args[i]
                else:
                    return default

            exec(self.lambdas.data[args[0]], locals(), globals())
            logging.info("@{0.author} -> {0.content}".format(message))

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
