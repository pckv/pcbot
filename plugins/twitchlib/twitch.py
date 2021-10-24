""" API wrapper for twitch.tv. """
import re

import discord

try:
    import twitchio
except ImportError:
    twitchio = None

from pcbot import Config

twitch_config = Config("twitch-api", data=dict(ids={}, client_id=None, client_secret=None))

# Define twitch API info
client_id = twitch_config.data["client_id"] or ""
client_secret = twitch_config.data["client_secret"] or ""

url_pattern = re.compile(r"^https://www.twitch.tv/(?P<name>.+)$")

if client_id and client_secret and twitchio:
    twitch_client = twitchio.Client.from_client_credentials(client_id=client_id, client_secret=client_secret)
else:
    twitch_client = None


class RequestFailed(Exception):
    """ For when the api request fails. """


class UserNotResolved(Exception):
    """ For when a name isn't resolved. """


async def get_stream(twitch_id: int):
    """ Get stream info from twitch API. """
    response = await twitch_client.fetch_streams(user_ids=[twitch_id])
    if len(response) == 0:
        raise RequestFailed
    return response[0]


async def get_videos(user_id: int):
    """ Return a user's archived videos sorted by time. """
    response = await twitch_client.fetch_videos(user_id=user_id, sort="time", type="archive")
    return response


async def get_id(member: discord.Member, name: str = None):
    """ Return a member's twitch user ID.

    If the name kwarg is omitted, the member should be connected to discord and
    already be streaming, so that member.activity.url can be used. When omitted and
    the member isn't streaming, a ValueError is raised.

    :param member: The member to return the ID for.
    :param name: Optionally specified twitch username of the member.
    :raises RequestFailed: Generic error when the request is refused.
    :raises UserNotResolved: Can't resolve member's twitch user.
    """
    # Return the cached id if this member has been checked before
    if str(member.id) in twitch_config.data["ids"]:
        return twitch_config.data["ids"][str(member.id)]

    # Try getting the name from the activity url if name is not specified
    if not name:
        url_found = False
        streaming_activity = None
        for activity in member.activities:
            # Raise NameResolveError if the name is unknown
            if activity and activity.type == discord.ActivityType.streaming and activity.url:
                url_found = True
                streaming_activity = activity

        if not url_found:
            raise UserNotResolved(f"Could not resolve twitch name of {member}: they are not streaming.")

        # Attempt finding the twitch name using the Member.activity object url
        match = url_pattern.match(streaming_activity.url)
        if match is None:
            raise UserNotResolved(f"Could not resolve twitch name of {member}: their url is broken.")
        name = match.group("name")

    # Make a request for the user found
    response = await twitch_client.fetch_users(names=[name])
    if len(response) == 0:
        raise UserNotResolved(
            f"Could not resolve twitch user account of {member}: twitch user {name} does not exist.")

    # Save and return the id
    twitch_id = str(response[0].id)
    twitch_config.data["ids"][str(member.id)] = twitch_id
    await twitch_config.asyncsave()
    return twitch_id
