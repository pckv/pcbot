""" Twitch notifier

This plugin updates twitch channels of any online users, notifying the server when they go live.

Commands:
!twitch
"""

import logging

import discord
import asyncio
import aiohttp

import bot
from pcbot import Config
from pcbot import download_file

commands = {
    "twitch": {
        "usage": "!twitch <option>\n"
                 "Options:\n"
                 "    set <username>\n"
                 "    get\n"
                 "    notify-channel [channel]",
        "desc": "Handle twitch commands.\n"
                "`set` assigns your twitch account for notifying.\n"
                "`get` returns a twitch channel link.\n"
                "~~`notify-channel` sets a channel as the notify channel. This channel should not be used by any "
                "member. Specify no channel to disable. **Requires `Manage Server` permission.**~~"
    }
}

twitch_channels = Config("twitch-channels", data={"channels": {}})
live_channels = {}
update_interval = 20  # Seconds

twitch_api = "https://api.twitch.tv/kraken"

logging.getLogger("requests").setLevel(logging.WARNING)


@asyncio.coroutine
def on_ready(client: bot.Bot):
    while True:
        try:
            yield from asyncio.sleep(update_interval)

            # Go through all set channels (if they're online on discord) and update their status
            for member_id, channel in twitch_channels.data["channels"].items():
                member = discord.utils.find(lambda m: m.status is not discord.Status.offline and m.id == member_id,
                                            client.get_all_members())

                if member:
                    with aiohttp.ClientSession() as session:
                        response = yield from session.get(twitch_api + "/streams/" + channel)
                        json = yield from response.json() if response.status == 200 else []

                    stream = json.get("stream")

                    if member_id in live_channels:
                        if not stream:
                            live_channels.pop(member_id)
                    else:
                        if stream:
                            live_channels[member_id] = stream

                            # Tell every mutual channel between the streamer and the bot that streamer started streaming
                            for server in client.servers:
                                if member in server.members:
                                    m = "{0} went live at {1[channel][url]}.\n" \
                                        "**{1[channel][display_name]}**: {1[channel][status]}\n" \
                                        "*Playing {1[game]}*".format(member.mention, stream)
                                    asyncio.async(client.send_message(server, m))

                                    preview = yield from download_file(stream["preview"]["medium"])
                                    yield from client.send_file(server, preview, filename="preview.jpg")
        except Exception as e:
            logging.info("Error: " + str(e))


@asyncio.coroutine
def on_command(client: bot.Bot, message: discord.Message, args: list):
    if args[0] == "!twitch":
        m = "Please see `!help twitch`."
        if len(args) > 1:
            # Assign a twitch channel to your name or remove it
            if args[1] == "set":
                if len(args) > 2:
                    twitch_channel = args[2]
                    twitch_channels.data["channels"][message.author.id] = twitch_channel
                    twitch_channels.save()
                    m = "Set your twitch channel to `{}`.".format(twitch_channel)
                else:
                    if message.author.id in twitch_channels.data["channels"]:
                        twitch_channels.data["channels"].pop(message.author.id)
                        twitch_channels.save()
                        m = "Twitch channel unlinked."

            # Return the member's or another member's twitch channel as a link
            elif args[1] == "get":
                if len(args) > 2:
                    member = client.find_member(message.server, args[2])
                else:
                    member = message.author

                if member:
                    # Send the link if member has set a channel
                    if member.id in twitch_channels.data["channels"]:
                        m = "{}'s twitch channel: https://secure.twitch.tv/{}.".format(
                            member.name,
                            twitch_channels.data["channels"][member.id]
                        )
                    else:
                        m = "No twitch channel assigned to {}!".format(member.name)
                else:
                    m = "Found no such member."

            # Set or get the twitch notify channel
            elif args[1] == "notify-channel":
                if message.author.permissions_in(message.channel).manage_server:
                    if len(args) > 2:
                        channel = client.find_channel(message.server, args[2])

                        if channel:
                            twitch_channels.data["notify-channel"] = channel.id
                            twitch_channels.save()
                            m = "Notify channel set to {}.".format(channel.mention)
                    else:
                        if "notify-channel" in twitch_channels.data:
                            twitch_channel = client.get_channel(twitch_channels.data["notify-channel"])
                            if twitch_channel:
                                m = "Twitch notify channel is {}.".format(twitch_channel)
                            else:
                                m = "The twitch notify channel no longer exists!"
                        else:
                            m = "A twitch notify channel has not been set."
                else:
                    m = "You need `Manage Server` to use this command."

        yield from client.send_message(message.channel, m)
