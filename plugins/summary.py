""" Plugin for generating markov text, or a summary if you will. """


import re
from collections import defaultdict
import random

import discord
import asyncio
import markovify

from pcbot import utils, Annotate
import plugins

# The messages stored per session, where every key is a channel id
stored_messages = defaultdict(list)
logs_from_limit = 5000
max_summaries = 5

# Define some regexes for option checking in "summary" command
valid_num = re.compile(r"\*(?P<num>\d+)")
valid_member = utils.member_mention_regex
valid_channel = utils.channel_mention_regex


class DiscordText(markovify.Text):
    """ Tries it's best to markovify discord/chat text. """
    def sentence_split(self, text: list):
        """ Takes a list, meaning it would already be split. """
        return text


@asyncio.coroutine
def update_messages(client: discord.Client, channel: discord.Channel):
    """ Get or update messages. """
    messages = stored_messages[channel.id]

    if messages:
        # If we have already stored some messages we will update with any new messages
        logged_messages = yield from client.logs_from(channel, after=messages[-1])
    else:
        # For our first time we want logs_from_limit messages
        logged_messages = yield from client.logs_from(channel, limit=logs_from_limit)

    # Add a reversed version of the logged messages, since they're logged backwards
    stored_messages[channel.id].extend(reversed(list(logged_messages)))


def is_valid_option(arg: str):
    if valid_num.match(arg) or valid_member.match(arg) or valid_channel.match(arg):
        return True

    return False


@plugins.command(usage="[*<num>] [@<user>] [#<channel>] [phrase ...]", pos_check=is_valid_option,
                 error="Please make a better decision next time.")
def summary(client: discord.Client, message: discord.Message, *options, phrase: Annotate.LowerContent=None):
    """ Perform a summary! """
    # This dict stores all parsed options as keywords
    member, channel, num = None, None, None
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
            assert not member
            member = utils.find_member(message.server, member_match.group())
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

    yield from client.send_typing(message.channel)
    yield from update_messages(client, channel)

    # Split the messages into content and filter member and phrase
    if member:
        message_content = [m.content for m in stored_messages[channel.id] if m.author == member]
    else:
        message_content = [m.content for m in stored_messages[channel.id]]
    if phrase:
        message_content = [s for s in message_content if phrase.lower() in s.lower()]

    model = DiscordText(message_content, state_size=1)

    for i in range(num):
        yield from client.say(message, model.make_sentence(tries=10000, max_overlap_ratio=1))
