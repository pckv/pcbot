""" PCBOT.

The main module which contains the Client. This is the module
that would be executed.
"""

import logging
import inspect
import os
from datetime import datetime
from getpass import getpass
from argparse import ArgumentParser
from traceback import print_exc

import discord
import asyncio

from pcbot import utils, config
import plugins

# Sets the version to enable accessibility for other modules
__version__ = config.set_version("PCBOT V3")


class Client(discord.Client):
    """ Custom Client class to hold the event dispatch override and
    some helper functions. """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.time_started = datetime.utcnow()
        self.last_deleted_messages = []

    async def _handle_event(self, func, event, *args, **kwargs):
        """ Handle the event dispatched. """
        try:
            result = await func(*args, **kwargs)
        except AssertionError as e:
            if not event == "message":
                await self.on_error(event, *args, **kwargs)

            # Find the message object and send the proper feedback
            message = args[0]
            await self.send_message(message.channel, str(e))
        except:
            await self.on_error(event, *args, **kwargs)
        else:
            if result is True and event == "message":
                log_message(args[0], prefix="... ")

    def dispatch(self, event, *args, **kwargs):
        # Exclude some messages
        if event == "message":
            message = args[0]
            if message.author == client.user:
                return
            if not message.content:
                return

        super().dispatch(event, *args, **kwargs)

        # We get the method name and look through our plugins' event listeners
        method = "on_" + event
        if method in plugins.events:
            for func in plugins.events[method]:
                client.loop.create_task(self._handle_event(func, event, *args, **kwargs))

    async def send_file(self, destination, fp, *, filename=None, content=None, tts=False):
        """ Override send_file to notify the server when an attachment could not be sent. """
        try:
            await super().send_file(destination, fp, filename=filename, content=content, tts=tts)
        except discord.errors.Forbidden:
            await self.send_message(destination, "*I don't have the permissions to send my attachment.*")

    async def delete_message(self, message):
        """ Override to add info on the last deleted message. """
        self.last_deleted_messages = [message]
        await super().delete_message(message)

    async def delete_messages(self, messages):
        """ Override to add info on the last deleted messages. """
        self.last_deleted_messages = list(messages)
        await super().delete_messages(messages)

    async def wait_for_message(self, timeout=None, *, author=None, channel=None, content=None, check=None, bot=False):
        """ Override the check with the bot keyword: if bot=False, the function
        won't accept messages from bot accounts, where if bot=True it doesn't care. """
        def new_check(message: discord.Message):
            return (check(message) if check is not None else True) and (True if bot else not message.author.bot)

        return await super().wait_for_message(timeout, author=author, channel=channel, content=content, check=new_check)

    @staticmethod
    async def say(message: discord.Message, content: str):
        """ Equivalent to client.send_message(message.channel, content) """
        msg = await client.send_message(message.channel, content)
        return msg


# Setup our client
client = Client()
autosave_interval = 60 * 30


async def autosave():
    """ Sleep for set time (default 30 minutes) before saving. """
    while not client.is_closed:
        await asyncio.sleep(autosave_interval)
        await plugins.save_plugins()
        logging.debug("Plugins saved")


def log_message(message: discord.Message, prefix: str=""):
    """ Logs a command/message. """
    logging.info("{prefix}@{author}{server} -> {content}".format(
        author=message.author,
        content=message.content.split("\n")[0],
        server=" ({})".format(message.server.name) if not message.channel.is_private else "",
        prefix=prefix,)
    )


async def execute_command(command: plugins.Command, message: discord.Message, *args, **kwargs):
    """ Execute a command and send any AttributeError exceptions. """
    app_info = await client.application_info()

    try:
        await command.function(message, *args, **kwargs)
    except AssertionError as e:
        await client.say(message, str(e) or command.error or utils.format_help(command))
    except:
        await client.say(message, "An error occurred while executing this command. If the error persists, "
                                       "please send a PM to {}.".format(app_info.owner))
        print_exc()


def default_self(anno, default, message: discord.Message):
    """ A silly function to make Annotate.Self work."""
    if default is utils.Annotate.Self:
        if anno is utils.Annotate.Member:
            return message.author
        elif anno is utils.Annotate.Channel:
            return message.channel

    return default


def parse_annotation(param: inspect.Parameter, default, arg: str, index: int, message: discord.Message):
    """ Parse annotations and return the command to use.

    index is basically the arg's index in shelx.split(message.content) """
    if default is param.empty:
        default = None

    if param.annotation is not param.empty:  # Any annotation is a function or Annotation enum
        anno = param.annotation

        # Valid enum checks
        if isinstance(anno, utils.Annotate):
            content = lambda s: utils.split(s, maxsplit=index)[-1].strip("\" ")

            if anno is utils.Annotate.Content:  # Split and get raw content from this point
                return content(message.content) or default
            elif anno is utils.Annotate.LowerContent:  # Lowercase of above check
                return content(message.content).lower() or default
            elif anno is utils.Annotate.CleanContent:  # Split and get clean raw content from this point
                return content(message.clean_content) or default
            elif anno is utils.Annotate.LowerCleanContent:  # Lowercase of above check
                return content(message.clean_content).lower() or default
            elif anno is utils.Annotate.Member:  # Checks member names or mentions
                return utils.find_member(message.server, arg) or default_self(anno, default, message)
            elif anno is utils.Annotate.Channel:  # Checks channel names or mentions
                return utils.find_channel(message.server, arg) or default_self(anno, default, message)
            elif anno is utils.Annotate.Code:  # Works like Content but extracts code
                return utils.get_formatted_code(utils.split(message.content, maxsplit=index)[-1]) or default

        try:  # Try running as a method
            result = anno(arg)
            return result if result is not None else default
        except TypeError:
            raise TypeError("Command parameter annotation must be either pcbot.utils.Annotate or a callable")
        except:  # On error, eg when annotation is int and given argument is str
            return None

    return str(arg) or default  # Return str of arg if there was no annotation


def parse_command_args(command: plugins.Command, cmd_args: list, message: discord.Message):
    """ Parse commands from chat and return args and kwargs to pass into the
    command's function. """
    signature = inspect.signature(command.function)
    args, kwargs = [], {}

    index = -1
    start_index = command.depth  # The index would be the position in the group
    num_kwargs = sum(1 for param in signature.parameters.values() if param.kind is param.KEYWORD_ONLY)
    num_required_kwargs = sum(1 for param in signature.parameters.values()
                              if param.kind is param.KEYWORD_ONLY and param.default is param.empty)
    pos_param = None
    num_given_kwargs = 0
    has_pos = any(param.kind is param.VAR_POSITIONAL for param in signature.parameters.values())
    num_pos_args = 0

    # Parse all arguments
    for param in signature.parameters.values():
        index += 1

        # Skip the first argument, as this is a message.
        if index == 0:
            continue

        # Any argument to fetch
        if index + 1 <= len(cmd_args):  # If there is an argument passed
            cmd_arg = cmd_args[index]
        else:
            if param.default is not param.empty:
                if param.kind is param.POSITIONAL_OR_KEYWORD:
                    args.append(default_self(param.annotation, param.default, message))
                elif param.kind is param.KEYWORD_ONLY:
                    kwargs[param.name] = default_self(param.annotation, param.default, message)

                if type(command.pos_check) is not bool:
                    index -= 1

                continue  # Move onwards once we find a default
            else:
                if num_pos_args == 0:
                    index -= 1
                break  # We're done when there is no default argument and none passed

        if param.kind is param.POSITIONAL_OR_KEYWORD:  # Parse the regular argument
            tmp_arg = parse_annotation(param, param.default, cmd_arg, index + start_index, message)

            if tmp_arg is not None:
                args.append(tmp_arg)
            else:
                return args, kwargs, False  # Force quit
        elif param.kind is param.KEYWORD_ONLY:  # Parse a regular arg as a kwarg
            # We want to override the default, as this is often handled by python itself.
            # It also seems to break some flexibility when parsing commands with positional arguments
            # followed by a keyword argument with it's default being anything but None.
            default = param.default if type(param.default) is utils.Annotate else None
            tmp_arg = parse_annotation(param, default, cmd_arg, index + start_index, message)

            if tmp_arg is not None:
                kwargs[param.name] = tmp_arg
                num_given_kwargs += 1
            else:  # It didn't work, so let's try parsing it as an optional argument
                if type(command.pos_check) is bool and pos_param:
                    tmp_arg = parse_annotation(pos_param, None, cmd_arg, index + start_index, message)

                    if tmp_arg is not None:
                        args.append(tmp_arg)
                        num_pos_args += 1
                        continue

                return args, kwargs, False  # Force quit
        elif param.kind is param.VAR_POSITIONAL:  # Parse all positional arguments
            if num_kwargs == 0 or type(command.pos_check) is not bool:
                end_search = None
            else:
                end_search = -num_kwargs
            pos_param = param

            for cmd_arg in cmd_args[index:end_search]:
                # Do not register the positional argument if it does not meet the optional criteria
                if type(command.pos_check) is not bool:
                    if not command.pos_check(cmd_arg):
                        break

                tmp_arg = parse_annotation(param, None, cmd_arg, index + start_index, message)

                # Add an option if it's not None. Since positional arguments are optional,
                # it will not matter that we don't pass it.
                if tmp_arg is not None:
                    args.append(tmp_arg)
                    num_pos_args += 1

            # Update the new index
            index += (num_pos_args - 1) if num_pos_args else -1

    # Number of required arguments are: signature variables - client and message
    # If there are no positional arguments, subtract one from the required arguments
    num_args = len(signature.parameters.items()) - 1
    if not num_required_kwargs:
        num_args -= (num_kwargs - num_given_kwargs)
    if has_pos:
        num_args -= int(not bool(num_pos_args))

    num_given = index  # Arguments parsed
    if has_pos:
        num_given -= (num_pos_args - 1) if not num_pos_args == 0 else 0

    complete = (num_given == num_args)

    # The command is incomplete if positional arguments are forced
    if complete and command.pos_check is True and num_pos_args == 0:
        complete = False

    # print(num_given, num_args)
    # print(args, kwargs)
    return args, kwargs, complete


async def parse_command(command: plugins.Command, cmd_args: list, message: discord.Message):
    """ Try finding a command """
    command = plugins.get_sub_command(command, cmd_args[1:])
    cmd_args = cmd_args[command.depth:]
    send_help = False

    # If the last argument ends with the help argument, skip parsing and display help
    if cmd_args[-1] in config.help_arg or (command.disabled_pm and message.channel.is_private):
        complete = False
        args, kwargs = [], {}
        send_help = True
    else:
        # Parse the command and return the parsed arguments
        args, kwargs, complete = parse_command_args(command, cmd_args, message)

    # If command parsing failed, display help for the command or the error message
    if not complete:
        log_message(message)  # Log the command

        if command.disabled_pm and message.channel.is_private:
            await client.say(message, "This command can not be executed in a private message.")
        else:
            if command.error and len(cmd_args) > 1 and not send_help:
                await client.say(message, command.error)
            else:
                if len(cmd_args) == 1:
                    send_help = True
                await client.say(message, utils.format_help(command, no_subcommand=False if send_help else True))

        command = None

    return command, args, kwargs


@client.event
async def on_ready():
    logging.info("Logged in as\n"
                 "{0.user} ({0.user.id})\n".format(client) +
                 "-" * len(client.user.id))


@client.event
async def on_message(message: discord.Message):
    """ What to do on any message received.

    The bot will handle all commands in plugins and send on_message to plugins using it. """
    # Make sure the client is ready before processing commands
    await client.wait_until_ready()

    start_time = datetime.now()

    # We don't care about channels we can't write in as the bot usually sends feedback
    if not message.channel.is_private and not message.server.me.permissions_in(message.channel).send_messages:
        return

    # Don't accept commands from bot accounts
    if message.author.bot:
        return

    # Split content into arguments by space (surround with quotes for spaces)
    cmd_args = utils.split(message.content)

    # Get command name
    cmd = ""
    if cmd_args[0].startswith(config.command_prefix) and len(cmd_args[0]) > len(config.command_prefix):
        cmd = cmd_args[0][len(config.command_prefix):]

    # Handle commands
    for plugin in plugins.all_values():
        # If there was a command and the bot can send messages in the channel, parse the command
        if not cmd:
            continue
        command = plugins.get_command(plugin, cmd)

        if command:
            parsed_command, args, kwargs = await parse_command(command, cmd_args, message)

            if parsed_command:
                log_message(message)  # Log the command
                client.loop.create_task(execute_command(parsed_command, message, *args, **kwargs))  # Run command

                # Log time spent parsing the command
                stop_time = datetime.now()
                time_elapsed = (stop_time - start_time).total_seconds() / 1000
                logging.debug("Time spent parsing command: {elapsed:.6f}ms".format(elapsed=time_elapsed))


async def add_tasks():
    """ Create any tasks for plugins' on_ready() coroutine and create task
    for autosaving. """
    await client.wait_until_ready()
    logging.info("Setting up background tasks.")

    # Call any on_ready function in plugins
    for plugin in plugins.all_values():
        if hasattr(plugin, "on_ready"):
            client.loop.create_task(plugin.on_ready())

    client.loop.create_task(autosave())


def main():
    """ The main function. Parses command line arguments, sets up logging,
    gets the user's login info, sets up any background task and starts the bot. """
    # Add all command-line arguments
    parser = ArgumentParser(description="Run PCBOT.")
    parser.add_argument("--version", "-V", help="Return the current version.",
                        action="version", version=__version__)

    # Setup a login group for handling only token or email, but not both
    login_group = parser.add_mutually_exclusive_group()
    login_group.add_argument("--token", "-t", help="The token to login with. Prompts if omitted.")
    login_group.add_argument("--email", "-e", help="The email to login to. Token prompt is default.")

    parser.add_argument("--new-pass", "-n", help="Always prompts for password.", action="store_true")
    parser.add_argument("--log-level", "-l",
                        help="Use the specified logging level (see the docs on logging for values).",
                        type=lambda s: getattr(logging, s.upper()), default=logging.INFO, metavar="LEVEL")
    start_args = parser.parse_args()

    # Setup logger with level specified in start_args or logging.INFO
    logging.basicConfig(level=start_args.log_level,
                        format="%(levelname)s %(asctime)s [%(module)s / %(name)s]: %(message)s")

    # Always keep discord.py logger at INFO as a minimum
    discord_logger = logging.getLogger("discord")
    discord_logger.setLevel(start_args.log_level if start_args.log_level >= logging.INFO else logging.INFO)

    # Setup some config for more customization
    bot_meta = config.Config("bot_meta", pretty=True, data=dict(
        name="PCBOT",
        command_prefix=config.command_prefix
    ))
    config.name = bot_meta.data["name"]
    config.command_prefix = bot_meta.data["command_prefix"]

    # Set the client for the plugins to use
    plugins.set_client(client)

    # Load plugin for builtin commands
    plugins.load_plugin("builtin", "pcbot")

    # Load all dynamic plugins
    plugins.load_plugins()

    # Handle login
    if not start_args.email:
        # Login with the specified token if specified
        token = start_args.token or input("Token: ")

        login = [token]
    else:
        # Get the email from commandline argument
        email = start_args.email

        password = ""
        cached_path = client._get_cache_filename(email)  # Get the name of the would-be cached email

        # If the --new-pass command-line argument is specified, remove the cached password
        # Useful for when you have changed the password
        if start_args.new_pass:
            if os.path.exists(cached_path):
                os.remove(cached_path)

        # Prompt for password if the cached file does not exist (the user has not logged in before or
        # they they entered the --new-pass argument)
        if not os.path.exists(cached_path):
            password = getpass()

        login = [email, password]

    # Setup background tasks
    client.loop.create_task(add_tasks())

    try:
        client.run(*login)
    except discord.errors.LoginFailure as e:
        logging.error(utils.format_exception(e))


if __name__ == "__main__":
    main()
