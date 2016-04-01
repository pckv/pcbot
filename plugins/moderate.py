""" Script for server moderation

If enabled on the server, spots any text containing the keyword nsfw and a link.
Then tries to delete their message, and post a link to the dedicated nsfw channel.

Commands:
!nsfwchannel
"""

import discord
import asyncio

from pcbot.config import Config

commands = {
    "nsfwchannel": {
        "usage": "!nsfwchannel <action>\n"
                 "Actions:\n"
                 "    set <channel>\n"
                 "    remove",
        "desc": "Sets a channel for nsfw content. **User requires `Manage Server` permission to use command.**\n"
                "*The bot requires `Manage Messages` permission to delete suspected NSFW content.*"
    }
}

always_run = True

moderate = Config("moderate", data={})


@asyncio.coroutine
def on_message(client: discord.Client, message: discord.Message, args: list):
    channel = moderate.data.get(message.server.id, {}).get("nsfw-channel")

    if args[0] == "!nsfwchannel":
        if message.author.permissions_in(message.channel).manage_server:
            m = "Please see `!help nsfwchannel`."
            if len(args) > 1:
                if args[1] == "set" and len(args) > 2:
                    if message.channel_mentions:
                        nsfw_channel = message.channel_mentions[0]

                        # Initialize the server moderation
                        if not moderate.data.get(message.server.id):
                            moderate.data[message.server.id] = {}

                        moderate.data[message.server.id]["nsfw-channel"] = nsfw_channel.id
                        moderate.save()
                        m = "Set server NSFW channel to {}".format(nsfw_channel.mention)
                elif args[1] == "remove":
                    if moderate.data.get(message.server.id, {}).get("nsfw-channel"):
                        moderate.data[message.server.id].pop("nsfw-channel")
                        moderate.save()
                        m = "Removed linked NSFW channel info."

            yield from client.send_message(message.channel, m)
        else:
            yield from client.send_message(message.channel, "You need `Manage Server` permission to use this command.")

    if channel:
        # Check if message includes keyword nsfw and a link
        msg = message.content.lower()
        if "nsfw" in msg and ("http://" in msg or "https://" in msg) and not message.channel == channel:
            if message.server.get_member(client.user.id).permissions_in(message.channel).manage_messages:
                yield from client.delete_message(message)

            nsfw_channel = message.server.get_channel(moderate.data[message.server.id].get("nsfw-channel"))

            if nsfw_channel:
                yield from client.send_message(message.channel, "{}: **Please post NSFW content in {}**".format(
                    message.author.mention, nsfw_channel.mention
                ))
            else:
                yield from client.send_message(message.channel, "{}: **I did not find the specified NSFW channel.** "
                                                                "If you wish to remove this feature, see `!help "
                                                                "nsfwchannel`.".format(message.server.owner.mention))
