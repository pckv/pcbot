""" Script for wordsearch

THIS SCRIPT IS INCOMPLETE.

Commands:
!wordsearch
"""

import discord
import asyncio

commands = {
    # "wordsearch": {
    #     "usage": "!wordsearch [action]\n"
    #              "Actions:\n"
    #              "    -a | --auto [words]\n"
    #              "    -s | --stop",
    #     "desc": "Start a wordsearch! Enter *any word* ending with `!` to guess the word!\n"
    #             "**Notice**: If your word is *before* in the dictionary, the set word would be after in the dictionary."
    # }
}

wordsearch = {}


@asyncio.coroutine
def on_command(client: discord.Client, message: discord.Message, args: list):
    if args[0] == "!wordsearch":
        if len(args) > 1:
            pass
