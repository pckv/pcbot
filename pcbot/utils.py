from enum import Enum
from functools import wraps
import shlex
import re

import discord
import asyncio
import aiohttp

from pcbot import Config

owner_cfg = Config("owner")


class Annotate(Enum):
    """ Command annotation enum.
    Annotate a command argument with one of these to get the commented value. """
    Content = 1  # Return all the content after command and/or arguments with Message.content
    CleanContent = 2  # Same as above but uses Message.clean_content
    User = Member = 3  # Return a member (uses find_member with steps=3)
    Channel = 4  # Return a channel (uses find_channel with steps=3)
    Code = 5  # Get formatted code (like Content but extracts any code)


def format_command_func(command: str):
    """ Return a formatted string representing the command function name. """
    return "cmd_" + command


def get_command(plugin, command: str):
    """ Find and return a command function from a plugin. """
    if not plugin.commands:  # Return None if the bot doesn't have any commands
        return None

    if command not in plugin.commands:  # Return None if the specified plugin doesn't have the specified command
        return None

    command = format_command_func(command)

    # Return the found command or None if plugin doesn't have the function
    return getattr(plugin, command, None)


def is_owner(user):
    """ Return true if user/member is the assigned bot owner. """
    if type(user) is not str:
        user = user.id

    if user == owner_cfg.data:
        return True

    return False


def owner(f):
    """ Decorator that runs the command only if the author is an owner. """
    @wraps(f)
    @asyncio.coroutine
    def decorator(client: discord.Client, message: discord.Message, *args, **kwargs):
        if is_owner(message.author):
            yield from f(client, message, *args, **kwargs)

    setattr(decorator, "__owner__", True)
    return decorator


@asyncio.coroutine
def download_file(url, **params):
    """ Download and return a byte-like object of a file.

    :param url: download url as str
    :param params: any additional url parameters. """
    with aiohttp.ClientSession() as session:
        response = yield from session.get(url,
                                          params=params)

        file = yield from response.read() if response.status == 200 else []

    return file


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


def format_exception(e):
    """ Returns a formatted string of Exception: str """
    return type(e).__name__ + ": " + str(e)


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


def split(string, maxsplit=-1):
    """ Split a string with shlex when possible, and add support for maxsplit. """
    if maxsplit == -1:
        try:
            return shlex.split(string)
        except ValueError:
            return string.split()

    split_object = shlex.shlex(string, posix=True)
    split_object.whitespace_split = True
    split_object.commenters = ""
    maxsplit_object = []
    splits = 0

    while splits < maxsplit:
        maxsplit_object.append(next(split_object))

        splits += 1

    maxsplit_object.append(split_object.instream.read())

    return maxsplit_object
