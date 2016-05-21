""" Script for server moderation

If enabled on the server, spots any text containing the keyword nsfw and a link.
Then tries to delete their message, and post a link to the dedicated nsfw channel.

Commands:
!nsfwchannel
"""

import discord
import asyncio

from pcbot.config import Config
import plugins

moderate = Config("moderate", data={}, load=False)


@asyncio.coroutine
def on_message(client: discord.Client, message: discord.Message, args: list):
    # Do not check in private mssages
    if message.channel.is_private:
        return False

    # Do not check if the channel is designed for nsfw content
    if "nsfw" not in message.channel.name:
        return False

    # Check if message includes keyword nsfw and a link
    msg = message.content.lower()
    if "nsfw" in msg and ("http://" in msg or "https://" in msg):
        if message.server.me.permissions_in(message.channel).manage_messages:
            yield from client.delete_message(message)

        nsfw_channel = discord.utils.find(lambda c: "nsfw" in c, message.server.channels)

        if nsfw_channel:
            yield from client.send_message(
                message.channel,
                "{0.mention}: **Please post NSFW content in {1.mention}**".format(message.author, nsfw_channel.mention)
            )

        return True

    return False
