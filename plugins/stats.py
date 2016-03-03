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
from operator import itemgetter

import discord
import asyncio

from pcbot import Config

commands = {
    "stats": {
        "usage": "!stats [member]",
        "desc": "Display various stats for this server.\n"
                "Mention a user to view user specific stats. Example: `!stats @Member`"
    }
}

stats = Config("stats", data={})


@asyncio.coroutine
def on_message(client: discord.Client, message: discord.Message, args: list):
    if client.user.id == message.author.id:
        return

    # Define any server and member not listed in stats
    if message.server.id not in stats.data:
        stats.data[message.server.id] = {}
    if message.author.id not in stats.data:
        stats.data[message.author.id] = {}

    # Format a record specific stat
    def format_record(record):
        r = stats.data[message.server.id].get(record)
        return "{0}\n" \
            "Letters typed: `{1[letters]}`\n" \
            "Words typed: `{1[words]}`\n" \
            "Channels/members mentioned: `{1[mentions]}`".format(message.server.get_member(r["author"]).name, r)

    # Format a record for user with most of a word
    def format_words(word):
        record = 0
        record_member = None
        for member in message.server.members:
            if stats.data.get(member.id):
                words = stats.data[member.id].get("word-count", {})
                if words.get(word, 0) > record:
                    record = words[word]
                    record_member = member

        return "{}\n" \
               "Count: `{}`".format(record_member.name, record)

    # User command
    if args[0] == "!stats":
        m = ""
        if len(args) > 1 and message.mentions:
            for member in message.mentions:
                if member.id in stats.data:
                    # Sort words descending
                    words = list(reversed(sorted(stats.data[member.id]["word-count"].items(), key=itemgetter(1))))
                    len_words = 10 if len(words) >= 10 else len(words)

                    m = "**{}'s {} most used words:**\n".format(member.mention, len_words)

                    # Add all data to our output
                    for i in range(len_words):
                        word = words[i]
                        m += "{}: `{}`\n".format(word[0], word[1])
                else:
                    m = "{} has never said anything.".format(member.mention)
        else:
            m = "**Stats:**\n" \
                "Letters typed: `{0[letters]}`\n" \
                "Words typed: `{0[words]}`\n" \
                "Pastas copypasted: `{0[pastas]}`\n" \
                "Channels/members mentioned: `{0[mentions]}`\n\n" \
                "**Records:**\n" \
                "__Longest message:__ {1}\n\n" \
                "__Most mentions in one message:__ {2}\n\n" \
                "__Most xD's total:__ {3}".format(stats.data[message.server.id],
                                                  format_record("longest-message"),
                                                  format_record("most-mentions"),
                                                  format_words("xd")
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

    # Log every word into a counter for the specific user
    if not stats.data[message.author.id].get("word-count"):
        stats.data[message.author.id]["word-count"] = {}

    for word in message.content.split():
        word = word.lower()
        stats.data[message.author.id]["word-count"][word] = (stats.data[message.author.id]["word-count"].get(word) or 0) + 1


@asyncio.coroutine
def save(client: discord.Client):
    stats.save()
