""" Script for basic commands

Commands:
!roll
!feature
"""

import random
from re import match

import discord
import asyncio

from pcbot import utils, Config, Annotate
import plugins


feature_reqs = Config(filename="feature_requests",
                      data={})


def get_req_id(feature_id: str):
    """ Return the id matched in an id string.
    Format should be similar to #24 """
    req_id = match("^#([0-9])+$", feature_id)

    if req_id:
        return int(req_id.group(1)) - 1

    return None


def format_req(plugin, req_id: int):
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


def plugin_in_req(plugin: str):
    """ Function for checking that the plugin exists and initializes the req.
    Returns the plugin name. """
    plugin = plugin.lower()

    if not plugins.get_plugin(plugin):
        return None

    if plugin not in feature_reqs.data:
        feature_reqs.data[plugin] = []

    return plugin


# Commands


@plugins.command(usage="[num | phrase]")
@asyncio.coroutine
def cmd_roll(client: discord.Client, message: discord.Message,
             max_roll: int=100):
    """ Roll a number from 1-100 if no second argument or second argument is not a number.
    Alternatively rolls `num` times. """
    roll = random.randint(1, max_roll)
    yield from client.send_message(message.channel, "{0.mention} rolls {1}".format(message.author, roll))


@asyncio.coroutine
def cmd_feature_list(client: discord.Client, message: discord.Message,
                     plugin: plugin_in_req):
    """ List all feature requests of a plugin. """
    format_list = "\n".join(format_req(plugin, req_id)
                            for req_id in range(len(feature_reqs.data[plugin])))

    if not format_list:
        yield from client.send_message(message.channel, "This plugin has no feature requests!")
        return

    # Format and display the feature requests of this plugin
    m = "```diff\n{list}```".format(list=format_list)
    yield from client.send_message(message.channel, m)


@asyncio.coroutine
def cmd_feature_id(client: discord.Client, message: discord.Message,
                   plugin: plugin_in_req, req_id: get_req_id) -> cmd_feature_list:
    """ Display feature request of id req_id of a plugin. """
    # Test and reply if feature by requested id doesn't exist
    if 0 > req_id >= len(feature_reqs.data[plugin]):
        yield from client.send_message(message.channel,
                                       "There is no such feature. Try `!feature {0}`.".format(plugin))

    # Format and send the feature request of the specified id
    yield from client.send_message(message.channel, "```diff\n" + format_req(plugin, req_id) + "```")


@asyncio.coroutine
def cmd_feature_new(client: discord.Client, message: discord.Message,
                    plugin: plugin_in_req, option: str.lower,
                    feature: Annotate.CleanContent) -> cmd_feature_id:
    """ Add a new feature request to a plugin. """
    if not option == "new":
        return

    req_list = feature_reqs.data[plugin]
    feature = feature.replace("\n", " ")

    if feature in req_list:
        yield from client.send_message(message.channel, "This feature has already been requested!")

    # Add the feature request if an identical request does not exist
    feature_reqs.data[plugin].append(feature)
    feature_reqs.save()

    yield from client.send_message(message.channel,
                                   "Feature saved as `{0}` id **#{1}**.".format(plugin, len(req_list)))


@plugins.command(usage="<plugin> [#feature_id | new <feature> | mark <#feature_id> | remove <#feature_id>]")
@utils.owner
@asyncio.coroutine
def cmd_feature(client: discord.Client, message: discord.Message,
                plugin: plugin_in_req, option: str.lower, req_id: get_req_id) -> cmd_feature_new:
    """ Handle plugin feature requests where plugin is a plugin name. See `!plugin` for a list of plugins.
    **Use none of the additional arguments** to see a list of feature requests for a plugin.
    `#feature_id` shows a plugin's feature request with the specified id.
    `new <feature>` is used to request a new plugin feature.
    `mark <#feature_id>` marks a feature as complete. **Owner command.**
    `remove <#feature_id>` removes a requested feature from the list entirely. **Owner command.**"""
    # Test and reply if feature by requested id doesn't exist
    if 0 > req_id >= len(feature_reqs.data[plugin]):
        yield from client.send_message(message.channel,
                                       "There is no such feature. Try `!feature {0}`.".format(plugin))

    if option == "mark":
        req = feature_reqs.data[plugin][req_id]

        # Mark or unmark the feature request by adding or removing +++ from the end (slightly hacked)
        if not req.endswith("+++"):
            feature_reqs.data[plugin][req_id] += "+++"
            feature_reqs.save()

            m = "Marked feature with `{}` id **#{}**.".format(plugin, req_id + 1)
        else:
            feature_reqs.data[plugin][req_id] = req[:-3]
            feature_reqs.save()

            m = "Unmarked feature with `{}` id **#{}**.".format(plugin, req_id + 1)
    elif option == "remove":
        feature_reqs.data[plugin].pop(req_id)
        feature_reqs.save()

        m = "Removed feature with `{}` id **#{}**.".format(plugin, req_id + 1)
    else:
        m = "`{0}` is not a valid option!".format(option)

    yield from client.send_message(message.channel, m)


@asyncio.coroutine
def on_message(client: discord.Client, message: discord.Message, _):
    # Have the bot reply confused whenever someone mentions it
    if not message.content.startswith("!") and client.user.id in [m.id for m in message.mentions]:
        phrases = ["what", "huh", "sorry", "pardon", "...", "!", "", "EH!", "wat", "excuse me", "really"]
        phrase = random.choice(phrases)
        if random.randint(0, 4) > 0:
            phrase += "?"

        yield from client.send_message(message.channel, phrase)

        return True

    return False
