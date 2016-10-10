""" Any utility functions.

This module holds the owner data along with a handful of
command specific functions and helpers.
"""

import re
import shlex
from enum import Enum
from functools import wraps
from io import BytesIO

import discord
import aiohttp

from pcbot import Config, config

owner_cfg = Config("owner")
member_mention_regex = re.compile(r"<@!?(?P<id>\d+)>")
channel_mention_regex = re.compile(r"<#(?P<id>\d+)>")
markdown_code_regex = re.compile(r"^(?P<capt>`*)(?:[a-z]+\n)?(?P<code>.+)(?P=capt)$", flags=re.DOTALL)
identifier_prefix = re.compile(r"[a-zA-Z_]")


class Annotate(Enum):
    """ Command annotation enum.
    Annotate a command argument with one of these to get the commented result. """
    Content = 1  # Return all the content after command and/or arguments with Message.content
    LowerContent = 2  # Same as above but returns the contents in lowercase
    CleanContent = 3  # Return all the content after command and/or arguments with Message.clean_content
    LowerCleanContent = 4  # Same as above but returns the contents in lowercase
    User = Member = 5  # Return a member (uses utils.find_member with steps=3)
    Channel = 6  # Return a channel (uses utils.find_channel with steps=3)
    Self = 7  # Used as a default for Member/Channel annotations and returns the message.author/message.channel
    Code = 8  # Get formatted code (like Content but extracts any code)


def int_range(f: int=None, t: int=None):
    """ Return a helper function for checking if a str converted to int is in the
    specified range, f (from) - t (to).

    If either f or t is None, they will be treated as -inf +inf respectively. """
    def wrapped(arg: str):
        # Convert to int and return None if unsuccessful
        try:
            num = int(arg)
        except ValueError:
            return None

        # Compare the lowest and highest numbers
        if (f and num < f) or (t and num > t):
            return None

        # The string given is converted to a number and fits the criteria
        return num

    return wrapped


def choice(*options, ignore_case: bool=True):
    """ Return a helper function for checking if the argument is either of the given
    options. """
    def wrapped(arg: str):
        # Compare lowercased version
        if ignore_case:
            return arg if arg.lower() in [s.lower() for s in options] else None

        return arg if arg in options else None

    return wrapped


def placeholder(_: str):
    """ Return False. Using this as a command argument annotation will always fail
    the command. Useful for groups. """
    return False


def format_usage(command):
    """ Format the usage string of the given command. Places any usage
    of a sub command on a newline.

    :param command: type plugins.Command """
    if command.hidden and command.parent is not None:
        return

    usage = [command.usage]
    for sub_command in command.sub_commands:
        # Recursively format the usage of the next sub commands
        formatted = format_usage(sub_command)

        if formatted:
            usage.append(formatted)

    return "\n".join(s for s in usage if s is not None) if usage else None


def format_help(command):
    """ Format the help string of the given command as a message to be sent.

    :param command: type plugins.Command """
    usage = format_usage(command)

    # If there is no usage, the command isn't supposed to be displayed as such
    # Therefore, we switch to using the parent command instead
    if usage is None and command.parent is not None:
        return format_help(command.parent)

    desc = command.description

    # Notify the user when a command is owner specific
    if getattr(command.function, "__owner__", False):
        desc += "\n:information_source:`Only the bot owner can execute this command.`"

    # Format aliases
    alias_format = ""
    if command.aliases:
        # Don't add blank space unless necessary
        if not desc.strip().endswith("```"):
            alias_format += "\n"

        alias_format += "**Aliases**: ```{}```".format(
            ", ".join((config.command_prefix if identifier_prefix.match(alias[0]) and command.parent is None else "") +
                      alias for alias in command.aliases))

    return "**Usage**: ```{}```**Description**: {}{}".format(usage, desc, alias_format)


def is_owner(member):
    """ Return true if user/member is the assigned bot owner.

    :param member: discord.User, discord.Member or a str representing the member's ID. """
    if type(member) is not str:
        member = member.id

    if member == owner_cfg.data:
        return True

    return False


def owner(func):
    """ Decorator that runs the command only if the author is the owner. """
    @wraps(func)
    async def wrapped(client: discord.Client, message: discord.Message, *args, **kwargs):
        if is_owner(message.author):
            await func(client, message, *args, **kwargs)

    setattr(wrapped, "__owner__", True)
    return wrapped


def permission(*perms: str):
    """ Decorator that runs the command only if the author has the specified permissions.
    perms must be a string matching any property of discord.Permissions. """
    def decorator(func):
        @wraps(func)
        async def wrapped(client: discord.Client, message: discord.Message, *args, **kwargs):
            member_perms = message.author.permissions_in(message.channel)

            if all(getattr(member_perms, perm, False) for perm in perms):
                await func(client, message, *args, **kwargs)

        return wrapped
    return decorator


def role(*roles: str):
    """ Decorator that runs the command only if the author has the specified Roles.
    roles must be a string representing a role's name. """
    def decorator(func):
        @wraps(func)
        async def wrapped(client: discord.Client, message: discord.Message, *args, **kwargs):
            member_roles = [r.name for r in message.author.roles[1:]]

            if any(r in member_roles for r in roles):
                await func(client, message, *args, **kwargs)

        return wrapped
    return decorator


async def retrieve_headers(url, **params):
    """ Retrieve the headers from a URL.

    :param url: URL as str
    :param params: Any additional url parameters
    :return: Headers as a dict """
    async with aiohttp.ClientSession() as session:
        async with session.head(url, params=params) as response:
            return response.headers


async def download_file(url, **params):
    """ Download and return a byte-like object of a file.

    :param url: Download url as str
    :param params: Any additional url parameters
    :return: The byte-like file """
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            return BytesIO(await response.read())


async def download_json(url, **params):
    """ Download and return a json file.

    :param url: Download url as str
    :param params: Any additional url parameters
    :return: A JSON representation of the downloaded file """
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            try:
                return await response.json()
            except ValueError:
                return None


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
    :param name: display_name as a string or mention to find.
    :param steps: int from 0-3 to specify search depth.
    :param mention: check for mentions. """
    member = None

    # Return a member from mention
    found_mention = member_mention_regex.search(name)
    if found_mention and mention:
        member = server.get_member(found_mention.group("id"))

    name = name.lower()

    if not member:
        # Steps to check, higher values equal more fuzzy checks
        checks = [lambda m: m.display_name.lower() == name,
                  lambda m: m.display_name.lower().startswith(name),
                  lambda m: name in m.display_name.lower()]

        for i in range(steps if steps <= len(checks) else len(checks)):
            member = discord.utils.find(checks[i], server.members)

            if member:
                break

    # Return the found member or None
    return member


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
    found_mention = channel_mention_regex.search(name)
    if found_mention and mention:
        channel = server.get_channel(found_mention.group("id"))

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


def get_member(client: discord.Client, member_id: str):
    """ Get a member from the specified ID. """
    for member in client.get_all_members():
        if member.id == member_id:
            return member

    return None


def format_exception(e):
    """ Returns a formatted string of Exception: e """
    return type(e).__name__ + ": " + str(e)


def format_syntax_error(e):
    """ Returns a formatted string of a SyntaxError.
    Stolen from https://github.com/Rapptz/RoboDanny/blob/master/cogs/repl.py#L24-L25 """
    return "{0.text}\n{1:>{0.offset}}\n{2}: {0}".format(e, "^", type(e).__name__)


def get_formatted_code(code):
    """ Format code from markdown format. This will filter out markdown code
    and give the executable python code, or return a string that would raise
    an error when it's executed by exec() or eval(). """
    match = markdown_code_regex.match(code)

    if match:
        code = match.group("code")

        if not code == "`":
            return code

    return "raise Exception(\"Could not format code.\")"


def format_objects(*objects: tuple, attr=None, dec: str= "", sep: str= ", "):
    """ Return a formatted string of objects (User, Member, Channel or Server) using
    the given decorator and the given separator.

    :param attr: The attribute to get from the member. """
    if not objects:
        return

    first_object = objects[0]
    if attr is None:
        if isinstance(first_object, discord.User):
            attr = "display_name"
        elif isinstance(first_object, discord.Channel):
            attr = "mention"
        elif isinstance(first_object, discord.Server):
            attr = "name"

    return sep.join(dec + getattr(m, attr) + dec for m in objects)


def format_channels(*members: discord.Member, attr="mention", dec: str = "`", sep: str = ", "):
    """ Return a formatted string of members (or member) using the given
    decorator and the given separator.

    :param attr: The attribute to get from the member. """
    return sep.join(dec + getattr(m, attr) + dec for m in members)


def split(string, maxsplit=-1):
    """ Split a string with shlex when possible, and add support for maxsplit. """
    if maxsplit == -1:
        try:
            split_object = shlex.shlex(string, posix=True)
            split_object.quotes = '"`'
            split_object.whitespace_split = True
            split_object.commenters = ""
            return list(split_object)
        except ValueError:
            return string.split()

    split_object = shlex.shlex(string, posix=True)
    split_object.quotes = '"`'
    split_object.whitespace_split = True
    split_object.commenters = ""
    maxsplit_object = []
    splits = 0

    while splits < maxsplit:
        maxsplit_object.append(next(split_object))

        splits += 1

    maxsplit_object.append(split_object.instream.read())

    return maxsplit_object
