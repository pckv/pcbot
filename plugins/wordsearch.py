""" Script for wordsearch

THIS SCRIPT IS INCOMPLETE.

Commands:
!wordsearch
"""

from re import match

import discord
import asyncio

commands = {
    "wordsearch": {
        "usage": "!wordsearch [action]\n"
                 "Actions:\n"
                 "    auto [words]\n"
                 "    stop",
        "desc": "Start a wordsearch! Enter *any word* ending with `!` to guess the word!\n"
                "~~`--auto` automatically sets a word for you.~~\n"
                "`--stop` stops a wordsearch in a channel. **This requires the `Manage Channel` permission.**\n\n"
                ":information_source: If your word is *before* in the dictionary, the set word would be after in the "
                "dictionary."
    }
}

wordsearch = []

TUTORIAL = "Write any word ending with `!` to guess the word!"
CHARACTER_MATCH = "[a-z0-9æøå]+"


def valid_word(message: discord.Message):
    """ Check if the word only contains norwegian style letters or numbers. """
    if match("^" + CHARACTER_MATCH + "$", message.content.lower()):
        if len(message.content) < 32:
            return True

    return False


def valid_guess(message: discord.Message):
    """ Check if a message in this channel is a word guess. """
    if match("^" + CHARACTER_MATCH + "!$", message.content.lower()):
        return True

    return False


def format_hint(hint):
    """ Formats the hint string for our messages. """
    return "The word starts with `{0}`.".format(hint) if hint else ""


def stop_wordsearch(channel: discord.Channel):
    wordsearch.remove(channel.id)


@asyncio.coroutine
def start_wordsearch(client: discord.Client, channel: discord.Channel, host: discord.Member):
    # Initialize the wordsearch
    wordsearch.append(channel.id)

    # Wait for the user to enter a word
    yield from client.send_message(host, "**Please enter a word!**\n"
                                         "The word should be **maximum 32 characters long** and "
                                         "may **only** contain `letters A-Å` and *numbers*.")
    reply = yield from client.wait_for_message(30, author=host, check=valid_word)

    # Stop the wordsearch if the user spent more than 30 seconds writing a valid word
    if not reply:
        stop_wordsearch(channel)
        yield from client.send_message(channel, "{0.mention} failed to enter a valid word.".format(host))
        return

    # Start the wordsearch
    word = reply.content.lower()
    yield from client.send_message(host, "Set the word to `{}`.".format(word))
    yield from client.send_message(channel, "{0.mention} has entered a word! ".format(host) + TUTORIAL)

    tries = 0
    hint = ""

    while channel.id in wordsearch:
        reply = yield from client.wait_for_message(60 * 30, channel=channel, check=valid_guess)

        # Wordsearch expires after 30 minutes
        if not reply:
            stop_wordsearch(channel)
            yield from client.send_message(channel, "**The wordsearch was cancelled after 30 minutes of inactivity.**\n"
                                                    "The word was `{}`.".format(word))
            return

        guessed_word = reply.content.lower()[:-1]
        tries += 1

        # Update hint
        if guessed_word.startswith(hint):
            hint = ""
            for i, c in enumerate(guessed_word):
                if len(word) - 1 < i:
                    break

                if not c == word[i]:
                    break

                hint += c

        # Compare the words
        if guessed_word > word:
            m = "{0.mention} `{1}` is *after* in the dictionary.".format(reply.author, guessed_word) + \
                format_hint(hint)
        elif guessed_word < word:
            m = "{0.mention} `{1}` is *before* in the dictionary.".format(reply.author, guessed_word) + \
                format_hint(hint)
        else:
            # User guessed the right word
            m = "{0.mention} ***got it*** after **{tries}** tries! The word was `{word}`.".format(reply.author,
                                                                                                  tries=tries,
                                                                                                  word=word)
            stop_wordsearch(channel)

        asyncio.async(client.send_message(channel, m))


@asyncio.coroutine
def on_command(client: discord.Client, message: discord.Message, args: list):
    if args[0] == "!wordsearch":
        if len(args) > 1:
            if args[1] == "auto":
                # TODO: Create automatic word setting.
                pass

            # Stop the wordsearch (does not start a wordsearch)
            #
            # THIS COMMAND WON'T WORK, CONSIDERING WE DON'T HAVE THE ASYNC LOOP (I may patch this though)
            #
            # elif args[1] == "stop":
            #     if message.author.permissions_in(message.channel).manage_channels:
            #         if message.channel.id in wordsearch:
            #             stop_wordsearch(message.channel)
            #             m = "The current wordsearch was cancelled."
            #         else:
            #             m = "There is no active wordsearch in this channel."
            #     else:
            #         m = "You need the `Manage Channel` permission to stop a wordsearch"
            #
            #     yield from client.send_message(message.channel, m)
            #     return

        # Start the wordsearch if there are none active in the channel
        # (starting includes includes waiting for a word from the user)
        if message.channel.id not in wordsearch:
            client.loop.create_task(start_wordsearch(client,
                                                     channel=message.channel,
                                                     host=message.author))
            m = "Waiting for {0.mention} to choose a word!".format(message.author)
        else:
            m = "A wordsearch is already active in this channel!"

        yield from client.send_message(message.channel, m)
