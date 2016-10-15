""" Plugin for generating markov text, or a summary if you will. """


import random
import re
from collections import defaultdict

import asyncio
import discord

from pcbot import utils, Annotate, config
import plugins
client = plugins.client  # type: discord.Client


# The messages stored per session, where every key is a channel id
stored_messages = defaultdict(list)
logs_from_limit = 5000
max_summaries = 5
update_task = asyncio.Event()
update_task.set()

# Define some regexes for option checking in "summary" command
valid_num = re.compile(r"\*(?P<num>\d+)")
valid_member = utils.member_mention_regex
valid_channel = utils.channel_mention_regex

on_no_messages = "**There were no messages to generate a summary from, {0.author.name}.**"
on_fail = "**I was unable to construct a summary, {0.author.name}.**"


async def update_messages(channel: discord.Channel):
    """ Get or update messages. """
    messages = stored_messages[channel.id]
    logged_messages = []
    update_task.clear()

    if messages:
        # If we have already stored some messages we will update with any new messages
        async for m in client.logs_from(channel, after=messages[-1]):
            logged_messages.append(m)
    else:
        # For our first time we want logs_from_limit messages
        async for m in client.logs_from(channel, limit=logs_from_limit):
            logged_messages.append(m)

    # Add a reversed version of the logged messages, since they're logged backwards
    stored_messages[channel.id].extend(reversed(list(logged_messages)))
    update_task.set()


def is_valid_option(arg: str):
    if valid_num.match(arg) or valid_member.match(arg) or valid_channel.match(arg):
        return True

    return False


def markov_messages(messages, coherent=False):
    """ Generate some kind of markov chain that somehow works with discord.
    I found this makes better results than markovify would. """
    imitated = []
    word = "@"

    # First word
    while (word.startswith("@") or "@" in word) or (word.startswith("http") or "http" in word):
        m_split = random.choice(messages).split()
        if not m_split:
            continue

        # Choose the first word in the sentence to simulate a markov chain
        word = m_split[0]

    # Add the first word
    imitated.append(word)

    # Next words
    while True:
        # Set the last word and find all messages with the last word in it
        im = imitated[-1].lower()
        valid = [m for m in messages if im in m.lower().split()]

        # Add a word from the message found
        if valid:
            m = random.choice(valid).split()  # Choose one of the matched messages and split it into a list
            m_indexes = [i for i, s in enumerate(m) if im == s.lower()]  # Get the indexes of all matched words
            m_index = random.choice(m_indexes)  # Choose a random index
            m_from = m[m_index:]

            # Are there more than the matched word in the message (is it not the last word?)
            if len(m_from) > 1:
                imitated.append(m_from[1])  # Then we'll add the next word
                continue
            else:
                # Have the chance of breaking be 1/4 at start and 1/1 when imitated approaches 150 words
                # unless the entire summary should be coherent
                chance = 0 if coherent else int(-0.02 * len(imitated) + 3)
                chance = chance if chance >= 0 else 0

                if random.randint(0, chance) == 0:
                    break

        # Add a random word
        while True:
            seq = random.choice(messages).split()

            if seq:
                word = random.choice(seq)
                imitated.append(word)
                break

    # Remove links after, because you know
    imitated = [s for s in imitated if "http://" not in s and "https://" not in s]

    return " ".join(imitated)


@plugins.command(usage="[*<num>] [@<user> ...] [#<channel>] [phrase ...]", pos_check=is_valid_option,
                 error="Please make a better decision next time.")
async def summary(message: discord.Message, *options, phrase: Annotate.LowerContent=None):
    """ Perform a summary! """
    # This dict stores all parsed options as keywords
    member, channel, num = [], None, None
    for value in options:
        num_match = valid_num.match(value)
        if num_match:
            assert not num
            num = int(num_match.group("num"))

            # Assign limits
            if num > max_summaries:
                num = max_summaries
            elif num < 1:
                num = 1
            continue

        member_match = valid_member.match(value)
        if member_match:
            member.append(utils.find_member(message.server, member_match.group()))
            continue

        channel_match = valid_channel.match(value)
        if channel_match:
            assert not channel
            channel = utils.find_channel(message.server, channel_match.group())
            continue

    # Assign defaults
    if not num:
        num = 1
    if not channel:
        channel = message.channel

    await client.send_typing(message.channel)
    await update_task.wait()
    await update_messages(channel)

    # Split the messages into content and filter member and phrase
    if member:
        message_content = [m.clean_content for m in stored_messages[channel.id] if m.author in member]
    else:
        message_content = [m.clean_content for m in stored_messages[channel.id]]
    if phrase:
        message_content = [s for s in message_content if phrase.lower() in s.lower()]

    # Clean up by removing all commands from the summaries
    if phrase is None or not phrase.startswith(config.command_prefix):
        message_content = [s for s in message_content if not s.startswith(config.command_prefix)]

    # Check if we even have any messages
    assert message_content, on_no_messages.format(message)

    # Generate the summary, or num summaries
    for i in range(num):
        sentence = markov_messages(message_content)
        await client.say(message, sentence or on_fail.format(message))
