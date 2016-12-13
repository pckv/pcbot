""" Plugin for generating markov text, or a summary if you will. """


import random
import re
from collections import defaultdict, deque
from functools import partial

import asyncio
import discord

from pcbot import utils, Annotate, config
import plugins
client = plugins.client  # type: discord.Client


# The messages stored per session, where every key is a channel id
stored_messages = defaultdict(partial(deque, maxlen=10000))
logs_from_limit = 5000
max_summaries = 5
update_task = asyncio.Event()
update_task.set()

# Define some regexes for option checking in "summary" command
valid_num = re.compile(r"\*(?P<num>\d+)")
valid_member = utils.member_mention_regex
valid_channel = utils.channel_mention_regex
valid_options = ("+re", "+regex", "+case", "+tts")

on_no_messages = "**There were no messages to generate a summary from, {0.author.name}.**"
on_fail = "**I was unable to construct a summary, {0.author.name}.**"


async def update_messages(channel: discord.Channel):
    """ Download messages. """
    messages = stored_messages[channel.id]  # type: deque

    # We only want to log messages when there are none
    # Any messages after this logging will be logged in the on_message event
    if messages:
        return

    # Make sure not to download messages twice by setting this handy task
    update_task.clear()

    # Download logged messages
    try:
        async for m in client.logs_from(channel, limit=logs_from_limit):
            if not m.content:
                continue

            # We have no messages, so insert each from the left, leaving us with the oldest at index -1
            messages.appendleft(m)
    except:  # When something goes wrong, clear the messages
        messages.clear()
    finally:  # Really have to make sure we clear this task in all cases
        update_task.set()


@plugins.event(bot=True)
async def on_message(message: discord.Message):
    """ Whenever a message is sent, see if we can update in one of the channels. """
    if message.channel.id in stored_messages and message.content:
        stored_messages[message.channel.id].append(message)


def is_valid_option(arg: str):
    if valid_num.match(arg) or valid_member.match(arg) or valid_channel.match(arg):
        return True

    if arg.lower() in valid_options:
        return True

    return False


def indexes_of_word(words: list, word: str):
    """ Return a list of indexes with the given word. """
    return [i for i, s in enumerate(words) if s.lower() == word]


def random_with_bias(messages: list, word: str):
    """ Go through all the messages and try to choose the ones where the given word is
    not at the end of the string. """
    last_word_messages = []
    non_last_word_messages = []
    for m in messages:
        words = m.split()
        if words[-1].lower() == word:
            last_word_messages.append(m)
        else:
            non_last_word_messages.append(m)

    if not last_word_messages:
        return random.choice(non_last_word_messages)
    elif not non_last_word_messages:
        return random.choice(last_word_messages)
    else:
        return random.choice(last_word_messages if random.randint(0, 5) == 0 else non_last_word_messages)


def markov_messages(messages, coherent=False):
    """ Generate some kind of markov chain that somehow works with discord.
    I found this makes better results than markovify would. """
    imitated = []
    word = ""

    if all(True if s.startswith("@") or s.startswith("http") else False for s in messages):
        return "**The given phrase would crash the bot.**"

    # First word
    while True:
        m_split = random.choice(messages).split()
        if not m_split:
            continue

        # Choose the first word in the sentence to simulate a markov chain
        word = m_split[0]

        if not word.startswith("@") and not word.startswith("http"):
            break

    # Add the first word
    imitated.append(word)
    valid = []
    im = ""

    # Next words
    while True:
        # Set the last word and find all messages with the last word in it
        if not im == imitated[-1].lower():
            im = imitated[-1].lower()
            valid = [m for m in messages if im in m.lower().split()]

        # Add a word from the message found
        if valid:
            # # Choose one of the matched messages and split it into a list or words
            m = random_with_bias(valid, im).split()
            m_indexes = indexes_of_word(m, im)
            m_index = random.choice(m_indexes)  # Choose a random index
            m_from = m[m_index:]

            # Are there more than the matched word in the message (is it not the last word?)
            if len(m_from) > 1:
                imitated.append(m_from[1])  # Then we'll add the next word
                continue
            else:
                # Have the chance of breaking be 1/4 at start and 1/1 when imitated approaches 150 words
                # unless the entire summary should be coherent
                chance = 0 if coherent else int(-0.02 * len(imitated) + 4)
                chance = chance if chance >= 0 else 0

                if random.randint(0, chance) == 0:
                    break

        # Add a random word if all valid messages are one word or there are less than 2 messages
        if len(valid) <= 1 or all(len(m.split()) <= 1 for m in valid):
            seq = random.choice(messages).split()
            word = random.choice(seq)
            imitated.append(word)

    # Remove links after, because you know
    imitated = [s for s in imitated if "http://" not in s and "https://" not in s]

    return " ".join(imitated)


def filter_messages(message_content: list, phrase: str, regex: bool=False, case: bool=False):
    """ Filter messages by searching and yielding each message. """
    for content in message_content:
        if regex:
            try:
                if re.search(phrase, content, 0 if case else re.IGNORECASE):
                    yield content
            except:  # Return error message when regex does not work
                raise AssertionError("**Invalid regex.**")
        elif not regex and (phrase in content if case else phrase.lower() in content.lower()):
            yield content


@plugins.command(usage="[*<num>] [@<user> ...] [#<channel>] [+re(gex)] [+case] [+tts] [phrase ...]",
                 pos_check=is_valid_option)
async def summary(message: discord.Message, *options, phrase: Annotate.Content=None):
    """ Perform a summary! """
    # This dict stores all parsed options as keywords
    member, channel, num = [], None, None
    regex, case, tts = False, False, False

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
            assert channel.permissions_for(message.server.me).read_message_history, "**I can't see this channel.**"
            continue

        if value in valid_options:
            if value == "+re" or value == "+regex":
                regex = True
            if value == "+case":
                case = True
            if value == "+tts":
                assert message.author.permissions_in(message.channel).send_tts_messages, \
                    "**You don't have permissions to send tts messages in this channel.**"
                tts = True

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
        message_content = list(filter_messages(message_content, phrase, regex, case))

    # Clean up by removing all commands from the summaries
    if phrase is None or not phrase.startswith(config.command_prefix):
        message_content = [s for s in message_content if not s.startswith(config.command_prefix)]

    # Check if we even have any messages
    assert message_content, on_no_messages.format(message)

    # Generate the summary, or num summaries
    for i in range(num):
        sentence = markov_messages(message_content)
        await client.send_message(message.channel, sentence or on_fail.format(message), tts=tts)
