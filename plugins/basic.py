""" Plugin for basic commands

Commands:
    roll
    feature
"""

import random
from re import match
from datetime import datetime, timedelta

import discord

from pcbot import utils, config, Config, Annotate, Cleverbot
import plugins
client = plugins.client  # type: discord.Client


feature_reqs = Config(filename="feature_requests", data={})
cleverbot = Cleverbot()


@plugins.command()
async def roll(message: discord.Message, num: utils.int_range(f=1)=100):
    """ Roll a number from 1-100 if no second argument or second argument is not a number.
        Alternatively rolls `num` times (minimum 1). """
    rolled = random.randint(1, num)
    await client.say(message, "{0.mention} rolls `{1}`.".format(message.author, rolled))


@plugins.command(description="Finds messages mentioning you in the last 24 hours.", aliases="mentions")
async def mentioned(message: discord.Message, member: Annotate.Member=Annotate.Self):
    """ Looks for member mentions. The description is in the decorator solely to
    correctly specify the type of member, so that PyCharm doesn't get cross.
    :type message: discord.Message
    :type member: discord.Member """
    after = datetime.utcnow() - timedelta(hours=24)
    was_found = False
    await client.send_typing(message.channel)

    # Go through all messages since 24 hours ago
    async for mention_message in client.logs_from(message.channel, limit=5000, before=message, after=after):
        if member not in mention_message.mentions:
            continue

        was_found = True

        # Format the message when it's found, along with messages from prior 15 seconds and latter 15 seconds
        after = mention_message.timestamp - timedelta(seconds=15)
        message_content = []
        async for nm in client.logs_from(message.channel, limit=50, after=after, before=after + timedelta(seconds=30)):
            if nm.author == mention_message.author:
                # Add an invisible separator and some spaces for an indent effect
                message_content.append("\N{INVISIBLE SEPARATOR}" + " " * 4 + nm.clean_content)

        found_message = await client.say(message, "**{0} - {1:%A, %d %B %Y %H:%M}**\n{2}".format(
            mention_message.author.display_name, after, "\n".join(reversed(message_content))))

        # The member will be able to search for another mention by typing next
        next_message = await client.say(message, "Type `next` to expand your search.")
        reply = await client.wait_for_message(timeout=30, author=member, channel=message.channel, content="next")

        # Remove the previously sent help message and break if there was no response
        if reply is None:
            await client.delete_message(next_message)
            break

        await client.delete_messages([found_message, reply, next_message])
        await client.send_typing(message.channel)
    else:
        await client.say(message, "{} mentioning you in the last 24 hours.".format(
            "Found no more messages" if was_found else "Could not find a message"))


@plugins.argument("#{open}feature_id{suffix}{close}")
def get_req_id(feature_id: str):
    """ Return the id matched in an id string.
    Format should be similar to #24 """
    req_id = match("^#?([0-9])+$", feature_id)
    assert req_id, "**Feature request id's must either be a number or follow `#<id>`**"

    return int(req_id.group(1)) - 1


def format_req(plugin, req_id: int):
    """ Format a request as checked or not checked, also displaying its ID. """
    req_list = feature_reqs.data[plugin]

    if 0 <= req_id < len(req_list):
        req = req_list[req_id]
        checked = "-"

        # Check if the request is marked
        if req.endswith("+++"):
            checked = "+"
            req = req[:-3]

        return "{checked} #{id:<4}| {req}".format(checked=checked, id=req_id + 1, req=req)

    return None


def feature_exists(plugin: str, req_id: str):
    """ Returns True if a feature with the given id exists. """
    return 0 <= req_id < len(feature_reqs.data[plugin])


def plugin_in_req(plugin: str):
    """ Function for checking that the plugin exists and initializes the req.
    Returns the plugin name. """
    plugin = plugin.lower()

    if not plugins.get_plugin(plugin):
        return None

    if plugin not in feature_reqs.data:
        feature_reqs.data[plugin] = []

    return plugin


@plugins.command()
async def feature(message: discord.Message, plugin: plugin_in_req, req_id: get_req_id=None):
    """ Handle plugin feature requests where plugin is a plugin name.
    See `{pre}plugin` for a list of plugins. """
    if req_id is not None:
        assert feature_exists(plugin, req_id), "There is no such feature."

        # The feature request the specified id exists, and we format and send the feature request
        await client.say(message, "```diff\n" + format_req(plugin, req_id) + "```")
    else:
        format_list = "\n".join(format_req(plugin, req_id)
                                for req_id in range(len(feature_reqs.data[plugin])))
        assert format_list, "This plugin has no feature requests!"

        # Format a list of all requests for the specified plugin when there are any
        await client.say(message, "```diff\n{list}```".format(list=format_list))


@feature.command()
async def new(message: discord.Message, plugin: plugin_in_req, content: Annotate.CleanContent):
    """ Add a new feature request to a plugin.
    See `{pre}plugin` for a list of plugins. """
    req_list = feature_reqs.data[plugin]
    content = content.replace("\n", " ")

    assert content not in req_list, "This feature has already been requested!"

    # Add the feature request if an identical request does not exist
    feature_reqs.data[plugin].append(content)
    feature_reqs.save()
    await client.say(message, "Feature saved as `{0}` id **#{1}**.".format(plugin, len(req_list)))


@feature.command()
@utils.owner
async def mark(message: discord.Message, plugin: plugin_in_req, req_id: get_req_id):
    """ Toggles marking a feature request as complete.
    See `{pre}plugin` for a list of plugins. """
    # Test and reply if feature by requested id doesn't exist
    assert feature_exists(plugin, req_id), "There is no such feature."

    req = feature_reqs.data[plugin][req_id]

    # Mark or unmark the feature request by adding or removing +++ from the end (slightly hacked)
    if not req.endswith("+++"):
        feature_reqs.data[plugin][req_id] += "+++"
        feature_reqs.save()
        await client.say(message, "Marked feature with `{}` id **#{}**.".format(plugin, req_id + 1))
    else:
        feature_reqs.data[plugin][req_id] = req[:-3]
        feature_reqs.save()
        await client.say(message, "Unmarked feature with `{}` id **#{}**.".format(plugin, req_id + 1))


@feature.command()
@utils.owner
async def remove(message: discord.Message, plugin: plugin_in_req, req_id: get_req_id):
    """ Removes a feature request.
    See `{pre}plugin` for a list of plugins. """
    # Test and reply if feature by requested id doesn't exist
    assert feature_exists(plugin, req_id), "There is no such feature."

    # Remove the feature
    del feature_reqs.data[plugin][req_id]
    feature_reqs.save()
    await client.say(message, "Removed feature with `{}` id **#{}**.".format(plugin, req_id + 1))


@plugins.event(bot=True)
async def on_message(message: discord.Message):
    """ Have cleverbot respond to our bot. """
    if not message.content.startswith(config.command_prefix) and client.user in message.mentions:
        # Start typing and remove the bot mention from the message.
        await client.send_typing(message.channel)
        question = " ".join(word for word in message.content.split() if not word == message.server.me.mention)

        # Ask cleverbot the given question and send the response.
        await client.say(message, await cleverbot.ask(question))
        return True
