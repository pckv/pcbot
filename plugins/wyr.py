""" Would you rather? This plugin includes would you rather functionality
"""

import random
import re

import discord

import plugins
from pcbot import utils, Config
client = plugins.client  # type: discord.Client


db = Config("would-you-rather", data=dict(timeout=10, responses=["**{name}** would **{choice}**!"], questions=[]), pretty=True)
command_pattern = re.compile(r"(.+)(?:\s+or|\s*,)\s+([^?]+)\?*")
sessions = set()  # All running would you rather's are in this set


@plugins.argument("{open}option ...{close} or/, {open}other option ...{close}[?]", allow_spaces=True)
async def options(arg):
    """ Command argument for receiving two options. """
    match = command_pattern.match(arg)
    assert match
    assert not match.group(1).lower() == match.group(2).lower(), "**The choices cannot be the same.**"

    return match.group(1), match.group(2)


@plugins.command(aliases="wyr rather either")
async def wouldyourather(message: discord.Message, opt: options=None):
    """ Ask the bot if he would rather, or have the bot ask you.

    **Example**: `!wouldyourather lie or be lied to`"""
    # If there are no options, the bot will ask the questions (if there are any to choose from)
    if opt is None:
        assert message.channel.id not in sessions, "**A would you rather session is already in progress.**"
        sessions.add(message.channel.id)

        assert db.data["questions"], "**There are ZERO questions saved. Ask me one!**"

        question = random.choice(db.data["questions"])
        choices = question["choices"]
        await client.say(message, "Would you rather **{}** or **{}**?".format(*choices))

        timeout = db.data["timeout"]
        replied = []

        # Wait for replies from anyone in the channel
        while True:
            reply = await client.wait_for_message(timeout=timeout, channel=message.channel,
                                                  check=lambda m: m.content.lower() in map(str.lower, choices) and
                                                                  m.author not in replied)
            if reply is None:
                break

            replied.append(reply.author)

            # Update the answers in the DB
            # We don't care about multiples, just the amount (yes it will probably be biased)
            if reply.content.lower() == choices[0]:
                question["answers"][0] += 1
            else:
                question["answers"][1] += 1

            name = reply.author.display_name
            response = random.choice(db.data["responses"]).format(name=name, NAME=name.upper(), choice=reply.content)
            await client.say(message, response)

        # Say the total tallies
        await client.say(message, "A total of {0} would **{2}**, while {1} would **{3}**!".format(
            *question["answers"], *choices))
        db.save()
        sessions.remove(message.channel.id)

    # Otherwise, the member asked a question to the bot
    else:
        db.data["questions"].append(dict(
            choices=list(opt),
            answers=[0, 0]
        ))
        db.save()

        answer = random.choice(opt)
        await client.say(message, "**I would {}**!".format(answer))


@wouldyourather.command(aliases="delete", owner=True)
async def remove(message: discord.Message, opt: options):
    """ Remove a wouldyourather question with the given options. """
    for q in db.data["questions"]:
        if q["choices"][0] == opt[0] and q["choices"][1] == opt[1]:
            db.data["questions"].remove(q)
            db.save()
            await client.say(message, "**Entry removed.**")
            break
    else:
        await client.say(message, "**Could not find the question.**")
