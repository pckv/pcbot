""" Script for logging statistics

Stats from messages:
    letters
    words
    mentions (both user and channel mentions)
    emojies
    pastas
    longest message
    most mentions


Commands:
!stats
"""

import re

import discord
import asyncio

from pcbot import Config

commands = {
    "stats": {
        "usage": "!stats",
        "desc": "Display various stats for this server."
    }
}

stats = Config("stats", data={})


@asyncio.coroutine
def on_message(client: discord.Client, message: discord.Message, args: list):
    if client.user.id == message.author.id:
        return

    # Define any server not listed in stats
    if message.server.id not in stats.data:
        stats.data[message.server.id] = {}

    def format_record(record):
        r = stats.data[message.server.id].get(record)
        m = "{0}\n" \
            "Letters typed: `{1[letters]}`\n" \
            "Words typed: `{1[words]}`\n" \
            "Channels/members mentioned: `{1[mentions]}`".format(message.server.get_member(r["author"]).name,
                                                                 r)

        return m

    if args[0] == "!stats":
        m = "**Stats:**\n" \
            "Letters typed: `{0[letters]}`\n" \
            "Words typed: `{0[words]}`\n" \
            "Pastas copypasted: `{0[pastas]}`\n" \
            "Channels/members mentioned: `{0[mentions]}`\n\n" \
            "**Records:**\n" \
            "__Longest message:__ {1}\n\n" \
            "__Most mentions in one message:__ {2}".format(stats.data[message.server.id],
                                                         format_record("longest-message"),
                                                         format_record("most-mentions")
                                                         )

        yield from client.send_message(message.channel, m)

    # Define stats
    letters = len(message.clean_content)
    words = len(message.clean_content.split())
    mentions = len(message.mentions) + len(message.channel_mentions)

    # Add stats to counter
    def add_stat(stat, value, default=0):
        stats.data[message.server.id][stat] = (stats.data[message.server.id].get(stat) or default) + value

    add_stat("letters", letters)
    add_stat("words", words)
    add_stat("mentions", mentions)

    if not stats.data[message.server.id].get("pastas"):
        stats.data[message.server.id]["pastas"] = 0

    if args[0] == "!pasta" or args[0].startswith("|"):
        add_stat("pastas", 1)

    message_stats = {
            "author": message.author.id,
            "letters": letters,
            "words": words,
            "mentions": mentions
    }

    # Check and add any beaten records
    if words > stats.data[message.server.id].get("longest-message", {}).get("words", 0):
        stats.data[message.server.id]["longest-message"] = message_stats

    if mentions > stats.data[message.server.id].get("most-mentions", {}).get("mentions", -1):
        stats.data[message.server.id]["most-mentions"] = message_stats


@asyncio.coroutine
def save(client: discord.Client):
    stats.save()
