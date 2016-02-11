""" Script template

Commands are specified by name, with keys usage and desc:
commands = {
    "cmd": {
        "usage": "!cmd <arg>",
        "desc": "Is a command."
    }
}

For on_message(), args is a list of all arguments split with shlex.

Commands: none
"""

import discord
import asyncio

commands = {

}


@asyncio.coroutine
def on_message(client: discord.Client, message: discord.Message, args: list):
    # Add any checks here.
    pass
