""" Twitch plugin for twitch notifications.

More to come?

Commands:
    twitch
"""

import logging
from datetime import datetime, timedelta

import discord

import bot
import plugins
from pcbot import utils, Config
from plugins.twitchlib import twitch

client = plugins.client  # type: bot.Client


twitch_config = Config("twitch-config", data=dict(guilds={}))

# Keep track of all {member.id: date} that are streaming
stream_history = {}
repeat_notification_delta = timedelta(hours=2)


async def on_reload(name):
    global stream_history
    local_history = stream_history

    await plugins.reload(name)

    stream_history = local_history


@plugins.command(name="twitch")
async def twitch_group(message: discord.Message, _: utils.placeholder):
    """ Administrative commands for twitch functions. Notifies when discord says you're streaming. """
    pass


@twitch_group.command(name="channels", permissions="manage_guild")
async def notify_channels(message: discord.Message, *channels: discord.TextChannel):
    """ Specify channels to notify when a member goes live, or use no arguments to disable. """
    if str(message.guild.id) not in twitch_config.data["guilds"]:
        twitch_config.data["guilds"][str(message.guild.id)] = {}

    twitch_config.data["guilds"][str(message.guild.id)]["notify_channels"] = [str(c.id) for c in channels]
    await twitch_config.asyncsave()

    # Tell the user if notifications were disabled
    assert channels, "**Disabled stream notifications in this guild.**"

    await client.say(message, "**Notifying streams in:** {}".format(utils.format_objects(*channels, sep=" ")))


def make_twitch_embed(member: discord.Member, response: dict):
    """ Return an embed of the twitch stream, using the twitch api response.

    :param member: Member object streaming.
    :param response: Dict received through twitch.request("streams").
    """
    streaming_activity = None
    for activity in member.activities:
        if activity is not None and (activity.type == discord.ActivityType.streaming and activity.platform.lower() ==
                                     "twitch"):
            streaming_activity = activity

    if streaming_activity is None:
        raise TypeError("No twitch stream found when making embed.")

    e = discord.Embed(title="Playing " + streaming_activity.game, url=streaming_activity.url,
                      description=streaming_activity.name, color=member.color)
    e.set_author(name=member.name, url=streaming_activity.url, icon_url=member.avatar_url)
    e.set_thumbnail(url=response["stream"]["preview"]["small"] + "?date=" + datetime.now().ctime().replace(" ", "%20"))
    return e


def started_streaming(before: discord.Member, after: discord.Member):
    """ Return True if the member just started streaming, and did not do so recently. """

    currently_streaming = False
    streamed_before = False

    # The member is streaming currently
    for activity in after.activities:
        if activity and activity.type == discord.ActivityType.streaming and hasattr(activity, "platform") \
                and activity.platform.lower() == "twitch":
            currently_streaming = True

    if not currently_streaming:
        return False

    # Check if they were also streaming before
    for activity in before.activities:
        if activity and activity.type == discord.ActivityType.streaming and hasattr(activity, "platform") \
                and activity.platform.lower() == "twitch":
            streamed_before = True

    if streamed_before:
        return False

    # Update the stream history
    previous_stream = stream_history.get(str(after.id))
    stream_history[str(after.id)] = datetime.now()

    # Check that they didn't start streaming recently
    if previous_stream and datetime.now() < (previous_stream + repeat_notification_delta):
        return False

    return True


@plugins.event()
async def on_member_update(before: discord.Member, after: discord.Member):
    """ Notify given channels whenever a member goes live. """

    # Make sure the member just started streaming
    if not started_streaming(before, after):
        return

    user = client.get_user(after.id)

    for guild in user.mutual_guilds:
        # Continue with next iteration if the guild doesn't have any notify channels setup
        if not twitch_config.data["guilds"].get(str(guild.id), {}).get("notify_channels", False):
            continue

        # Tru getting the id and also log some possibly useful info during exceptions
        try:
            twitch_id = await twitch.get_id(after)
        except twitch.RequestFailed as e:  # Could not find the streamer due to a request error
            logging.info("Could not get twitch id of {}: {}".format(after, e))
            return
        except twitch.UserNotResolved as e:  # Ignore them if the id was not found.
            logging.debug(e)
            return

        # Return the stream info of the specified user
        try:
            stream_response = await twitch.request("streams/" + twitch_id)
        except twitch.RequestFailed as e:
            logging.info("Could not get twitch stream of {} (id: {}): {}".format(after, twitch_id, e))
            return

        # If the member isn't actually streaming, return (should not be the case as discord uses the twitch api too)
        if stream_response["stream"] is None:
            return

        # Create the embedded message and send it to every stream channel
        embed = make_twitch_embed(after, stream_response)
        for channel_id in twitch_config.data["guilds"][str(guild.id)]["notify_channels"]:
            await client.send_message(guild.get_channel(int(channel_id)), embed=embed)

