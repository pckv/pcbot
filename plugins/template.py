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
def on_command(client: discord.Client, message: discord.Message, args: list):
    # Add any checks here.
    pass


@asyncio.coroutine
def save(client: discord.Client):
    # Optionally, add anything that should be saved here (eg configs)
    # Feel free to remove this function when it's not needed
    pass
