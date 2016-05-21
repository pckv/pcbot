""" Script for server moderation

If enabled on the server, spots any text containing the keyword nsfw and a link.
Then tries to delete their message, and post a link to the dedicated nsfw channel.

Commands:
!moderate
"""

from collections import defaultdict

import discord
import asyncio

from pcbot.config import Config
import plugins

moderate = Config("moderate", data=defaultdict(dict))

default_config = dict(
    nsfwfilter=True
)


def setup_default_config(server: discord.Server):
    """ Setup default settings for a server. """
    # Set to defaults if there is no config for the server
    if server.id not in moderate.data:
        moderate.data[server.id] = default_config
        moderate.save()
        return

    # Set to defaults if server's config is missing values
    if not all(k in default_config for k in moderate.data[server.id].keys()):
        moderate.data[server.id] = default_config
        moderate.save()


@plugins.command(name="moderate", usage="<nsfwfilter <on | off>>")
def moderate_(client: discord.Client, message: discord.Message, setting: str.lower):
    """ Change moderation settings. """
    yield from client.say(message, "No setting `{}`.".format(setting))


@moderate_.command()
def nsfwfilter(client: discord.Client, message: discord.Message, option: str.lower=None):
    """ Change NSFW filter settings. """
    if option == "on":  # Enable filter
        moderate.data[message.server.id]["nsfwfilter"] = True
        moderate.save()
        yield from client.say(message, "NSFW filter enabled.")
    elif option == "off":  # Disable filter
        moderate.data[message.server.id]["nsfwfilter"] = False
        moderate.save()
        yield from client.say(message, "NSFW filter disabled.")
    else:  # Show current setting
        setup_default_config(message.server)
        current = moderate.data[message.server.id]["nsfwfilter"]
        yield from client.say(message, "NSFW filter is `{}`.".format("ON" if current else "OFF"))


@asyncio.coroutine
def on_message(client: discord.Client, message: discord.Message, args: list):
    # Do not check in private messages
    if message.channel.is_private:
        return False

    setup_default_config(message.server)

    # Check if this server has nsfwfilter enabled
    if not moderate.data[message.server.id]["nsfwfilter"]:
        return False

    # Do not check if the channel is designed for nsfw content
    if "nsfw" in message.channel.name:
        return False

    # Check if message includes keyword nsfw and a link
    msg = message.content.lower()
    if "nsfw" in msg and ("http://" in msg or "https://" in msg):
        if message.server.me.permissions_in(message.channel).manage_messages:
            yield from client.delete_message(message)

        nsfw_channel = discord.utils.find(lambda c: "nsfw" in c.name, message.server.channels)

        if nsfw_channel:
            yield from client.send_message(
                message.channel,
                "{0.mention}: **Please post NSFW content in {1.mention}**".format(message.author, nsfw_channel)
            )

        return True

    return False
