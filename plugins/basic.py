""" Plugin for basic commands

Commands:
    roll
    feature
"""

import random
from re import match
from datetime import datetime, timedelta

import discord

from pcbot import utils, Config, Annotate
import plugins


feature_reqs = Config(filename="feature_requests", data={})


@plugins.command()
def roll(client: discord.Client, message: discord.Message, num: utils.int_range(f=1)=100):
    """ Roll a number from 1-100 if no second argument or second argument is not a number.
        Alternatively rolls `num` times (minimum 1). """
    rolled = random.randint(1, num)
    yield from client.say(message, "{0.mention} rolls `{1}`.".format(message.author, rolled))


@plugins.command(aliases="whomentionedme")
def mentioned(client: discord.Client, message: discord.Message):
    """ Tries to find the first message which mentions you in the last 16 hours. """
    after = datetime.utcnow() - timedelta(minutes=20)
    log = yield from client.logs_from(message.channel, limit=5000, after=after)
    print(len(list(log)))

    for m in log:
        if message.author in m.mentions:
            yield from client.say(message, "**{0.author.display_name} - {1}**\n{0.clean_content}".format(
                m, m.timestamp.strftime("%A, %d %B %Y %H:%M:%S")))
            break
    else:
        yield from client.say(message, "Could not find a message mentioning you in the last 16 hours.")


@plugins.argument("#{open}feature_id{suffix}{close}")
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
def feature(client: discord.Client, message: discord.Message, plugin: plugin_in_req, req_id: get_req_id=None):
    """ Handle plugin feature requests where plugin is a plugin name. See `!plugin` for a list of plugins.

        `#feature_id` shows a plugin's feature request with the specified id.  /
        `new <feature>` is used to request a new plugin feature.  /
        `mark <#feature_id>` marks a feature as complete. **Owner command.**  /
        `remove <#feature_id>` removes a requested feature from the list entirely. **Owner command.**"""

    if req_id is not None:
        assert feature_exists(plugin, req_id), "There is no such feature."

        # The feature request the specified id exists, and we format and send the feature request
        yield from client.say(message, "```diff\n" + format_req(plugin, req_id) + "```")
    else:
        format_list = "\n".join(format_req(plugin, req_id)
                                for req_id in range(len(feature_reqs.data[plugin])))
        assert format_list, "This plugin has no feature requests!"

        # Format a list of all requests for the specified plugin when there are any
        yield from client.say(message, "```diff\n{list}```".format(list=format_list))


@feature.command()
def new(client: discord.Client, message: discord.Message, plugin: plugin_in_req, content: Annotate.CleanContent):
    """ Add a new feature request to a plugin. """
    req_list = feature_reqs.data[plugin]
    content = content.replace("\n", " ")

    assert content not in req_list, "This feature has already been requested!"

    # Add the feature request if an identical request does not exist
    feature_reqs.data[plugin].append(content)
    feature_reqs.save()
    yield from client.say(message, "Feature saved as `{0}` id **#{1}**.".format(plugin, len(req_list)))


@feature.command()
@utils.owner
def mark(client: discord.Client, message: discord.Message, plugin: plugin_in_req, req_id: get_req_id):
    """ Toggles marking a feature request as complete. """
    # Test and reply if feature by requested id doesn't exist
    assert feature_exists(plugin, req_id), "There is no such feature."

    req = feature_reqs.data[plugin][req_id]

    # Mark or unmark the feature request by adding or removing +++ from the end (slightly hacked)
    if not req.endswith("+++"):
        feature_reqs.data[plugin][req_id] += "+++"
        feature_reqs.save()
        yield from client.say(message, "Marked feature with `{}` id **#{}**.".format(plugin, req_id + 1))
    else:
        feature_reqs.data[plugin][req_id] = req[:-3]
        feature_reqs.save()
        yield from client.say(message, "Unmarked feature with `{}` id **#{}**.".format(plugin, req_id + 1))


@feature.command()
@utils.owner
def remove(client: discord.Client, message: discord.Message, plugin: plugin_in_req, req_id: get_req_id):
    """ Removes a feature request. """
    # Test and reply if feature by requested id doesn't exist
    assert feature_exists(plugin, req_id), "There is no such feature."

    # Remove the feature
    del feature_reqs.data[plugin][req_id]
    feature_reqs.save()
    yield from client.say(message, "Removed feature with `{}` id **#{}**.".format(plugin, req_id + 1))


@plugins.event()
def on_message(client: discord.Client, message: discord.Message):
    # Have the bot reply confused whenever someone mentions it
    if not message.content.startswith("!") and client.user.id in [m.id for m in message.mentions]:
        phrases = ["what", "huh", "sorry", "pardon", "...", "!", "", "EH!", "wat", "excuse me", "really"]
        phrase = random.choice(phrases)
        if random.randint(0, 4) > 0:
            phrase += "?"

        yield from client.send_message(message.channel, phrase)

        return True
