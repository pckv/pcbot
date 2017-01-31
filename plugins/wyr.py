""" Would you rather? This plugin includes would you rather functionality
"""

import random
import re

import discord

import plugins
from pcbot import Config
client = plugins.client  # type: discord.Client


db = Config("would-you-rather", data=dict(timeout=10, responses=["Registered {choice}, {name}!"], questions=[]), pretty=True)
command_pattern = re.compile(r"(.+)(?:\s+or|\s*,)\s+([^?]+)\?*")


@plugins.argument("{open}option ...{close} or/, {open}other option ...{close}[?]", allow_spaces=True)
async def options(arg):
    """ Command argument for receiving two options. """
    match = command_pattern.match(arg)
    assert match

    return match.group(1), match.group(2)


@plugins.command(aliases="wyr rather either")
async def wouldyourather(message: discord.Message, opt: options=None):
    """ Ask the bot if he would rather, or have the bot ask you.

    **Example**: `!wouldyourather lie or be lied to`"""
    # If there are no options, the bot will ask the questions (if there are any to choose from)
    if opt is None:
        assert db.data["questions"], "**There are ZERO questions saved. Ask me one!**"

        question = random.choice(db.data["questions"])
        choices = question["choices"]
        await client.say(message, "Would you rather **{}** or **{}**?".format(*choices))

        timeout = db.data["timeout"]
        replied = []

        # Wait for replies from anyone in the channel
        while True:
            reply = await client.wait_for_message(timeout=timeout, channel=message.channel,
                                                  check=lambda m: m.content.lower() in choices and m.author not in replied)
            if reply is None:
                break

            # Update the answers in the DB
            # We don't care about multiples, just the amount (yes it will probably be biased)
            if reply.content.lower() == choices[0]:
                question["answers"][0] += 1
            else:
                question["answers"][1] += 1

            name = reply.author.display_name
            response = random.choice(db.data["responses"]).format(name=name, NAME=name.upper(), choice=reply.content)
            await client.say(message, "**{}**".format(response))

        # Say the total tallies
        await client.say(message, "A total of {0} would **{2}**, while {1} would **{3}**!".format(
            *question["answers"], *choices))
        db.save()

    # Otherwise, the member asked a question to the bot
    else:
        db.data["questions"].append(dict(
            choices=list(opt),
            answers=[0, 0]
        ))
        db.save()

        answer = random.choice(opt)
        await client.say(message, "**I would {}**!".format(answer))

