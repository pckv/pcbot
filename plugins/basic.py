""" Script for basic commands

Commands:
!ping
!cool
!pasta
"""

import random
import logging
from re import match

from datetime import datetime

import discord
import asyncio

from pcbot import Config


commands = {
    "ping": {
        "usage": "!ping",
        "desc": "Pong"
    },
    "roll": {
        "usage": "!roll [num | phrase]",
        "desc": "Roll a number from 1-100 if no second argument or second argument is not a number.\n"
                "Alternatively rolls *num* times."
    },
    "feature": {
        "usage": "!feature <plugin> <#feature_id | list | new <feature> | mark <#feature_id> | remove <#feature_id>>",
        "desc": "Handle plugin features where plugin is a plugin name. To find #feature_id, check `list`."
                "`list [#feature_id]` gives a list of requested features and whether they're added or not.\n"
                "`new <feature>` is used to request a new plugin feature.\n"
                "`mark <#feature_id>` marks a feature as complete. **Owner command.**\n"
                "`remove <#feature_id>` removes a requested feature from the list entirely. **Owner command.**"
    },
}

feature_reqs = Config(filename="feature_requests",
                      data={})


def get_req_id(feature_id: str):
    """ Return the id matched in an id string.
    Format should be similar to #24 """
    req_id = match("^#([0-9])+$", feature_id)

    if req_id:
        return int(req_id.group(1)) - 1

    return False


def format_req(plugin, req_id: int):
    req_list = feature_reqs.data[plugin]

    if 0 <= req_id < len(req_list):
        req = req_list[req_id]
        checked = "-"

        # Check if the request is marked
        if req.endswith("+++"):
            checked = "+"
            req = req[:-3]

        return "{checked} #{id:<4}| {req}".format(checked=checked,
                                                  id=req_id + 1,
                                                  req=req)

    return None


@asyncio.coroutine
def on_command(client: discord.Client, message: discord.Message, args: list):
    # Basic check
    if args[0] == "!ping":
        start = datetime.now()
        pong = yield from client.send_message(message.channel, "pong")
        end = datetime.now()
        response = (end - start).microseconds / 1000
        yield from client.edit_message(pong, "pong `{}ms`".format(response))

        logging.info("Response time: {}ms".format(response))

    # Roll from 1-100 or more
    elif args[0] == "!roll":
        if len(args) > 1:
            try:
                roll = random.randint(1, int(args[1]))
            except ValueError:
                roll = random.randint(1, 100)
        else:
            roll = random.randint(1, 100)

        yield from client.send_message(message.channel, "{0.mention} rolls {1}".format(message.author, roll))

    # Handle bot feature requests
    # (warning: this code is not representative of what I stand for in programming. I'm sorry.)
    elif args[0] == "!feature":
        m = "Please see `!help feature`."
        if len(args) > 2:
            plugin = args[1]
            if client.has_plugin(plugin):
                # Initialize the plugin for features
                if plugin not in feature_reqs.data:
                    feature_reqs.data[plugin] = []

                req_list = feature_reqs.data[plugin]

                # List feature request
                if args[2].startswith("#"):
                    feature_id = get_req_id(args[2])

                    if feature_id is not None:
                        if 0 <= feature_id < len(req_list):
                            m = "```diff\n" + format_req(plugin, feature_id) + "```"
                        else:
                            m = "There is no such feature. Try `!feature {} list`.".format(plugin)

                # List all feature requests or request with given ID.
                if args[2] == "list":
                    m = "```diff\n"
                    for req_id in range(len(req_list)):
                        m += format_req(plugin, req_id) + "\n"

                    m += "```"

                # Create a new feature
                elif args[2] == "new" or args[2] == "add" and len(args) > 3:
                    feature = " ".join(args[3:]).replace("\n", " ")

                    if feature not in req_list:
                        feature_reqs.data[plugin].append(feature)
                        feature_reqs.save()

                        m = "Feature saved as `{}` id **#{}**.".format(plugin, len(req_list))

                # Owner commands
                if client.is_owner(message.author):
                    # Mark a feature as complete
                    if args[2] == "mark" and len(args) > 3:
                        feature_id = get_req_id(args[3])

                        if feature_id is not None:
                            if 0 <= feature_id < len(req_list):
                                req = feature_reqs.data[plugin][feature_id]

                                if not req.endswith("+++"):
                                    feature_reqs.data[plugin][feature_id] += "+++"
                                    feature_reqs.save()

                                    m = "Marked feature with `{}` id **#{}**.".format(plugin, feature_id + 1)
                                else:
                                    feature_reqs.data[plugin][feature_id] = req[:-3]
                                    feature_reqs.save()

                                    m = "Unmarked feature with `{}` id **#{}**.".format(plugin, feature_id + 1)
                            else:
                                m = "There is no such feature. Try `!feature {} list`.".format(plugin)

                    # Remove a feature request
                    elif args[2] == "remove"and len(args) > 3:
                        feature_id = get_req_id(args[3])

                        if feature_id is not None:
                            if 0 <= feature_id < len(req_list):
                                feature_reqs.data[plugin].pop(feature_id)
                                feature_reqs.save()

                                m = "Removed feature with `{}` id **#{}**.".format(plugin, feature_id + 1)
                            else:
                                m = "There is no such feature. Try `!feature {} list`.".format(plugin)

            else:
                m = "Found no such plugin. Ask the bot owner if you are confused."

        yield from client.send_message(message.channel, m)


@asyncio.coroutine
def on_message(client: discord.Client, message: discord.Message, args: list):
    # Have the bot reply confused whenever someone mentions it
    if not message.content.startswith("!") and client.user.id in [m.id for m in message.mentions]:
        phrases = ["what", "huh", "sorry", "pardon", "...", "!", "", "EH!", "wat", "excuse me", "really"]
        phrase = random.choice(phrases)
        if random.randint(0, 4) > 0:
            phrase += "?"

        yield from client.send_message(message.channel, phrase)

        return True

    return False
