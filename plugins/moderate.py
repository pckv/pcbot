""" Script for server moderation

If enabled on the server, spots any text containing the keyword nsfw and a link.
Then tries to delete their message, and post a link to the dedicated nsfw channel.

Commands:
!moderate
!mute
!unmute
!timeout
"""

from collections import defaultdict

import discord
import asyncio

from pcbot import Config, utils, Annotate
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


def get_muted_role(server: discord.Server):
    """ Return the server's Muted role or None. """
    for role in server.roles:
        if role.name == "Muted":
            return role

    return None


@asyncio.coroutine
def manage_mute(client: discord.Client, message: discord.Message, function, *members: discord.Member):
    """ Add or remove Muted role for given members.

    Function is either client.add_roles or client.remove_roles. """
    # Manage Roles is required to add or remove the Muted role
    if not message.server.me.permissions_in(message.channel).manage_roles:
        yield from client.say(message, "I need `Manage Roles` permission to use this command.")
        return False

    muted_role = get_muted_role(message.server)

    # The server needs to properly manage the Muted role
    if not muted_role:
        yield from client.say(message, "No role assigned for muting. Please create a `Muted` role.")
        return False

    # Try giving members the Muted role
    for member in members:
        if member is message.server.me:
            yield from client.say(message, "I refuse to mute myself!")
            continue

        while True:
            try:
                yield from function(member, muted_role)
                break
            except discord.errors.Forbidden:
                yield from client.say(message, "I do not have permission to give members the `Muted` role.")
                return False
            except discord.errors.HTTPException:
                continue

    return True


@plugins.command(name="moderate", usage="<nsfwfilter <on | off>>")
def moderate_(client: discord.Client, message: discord.Message, setting: str.lower):
    """ Change moderation settings. """
    yield from client.say(message, "No setting `{}`.".format(setting))


@moderate_.command()
@utils.permission("manage_server")
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


@plugins.command(usage="<users ...>")
@utils.permission("manage_messages")
def mute(client: discord.Client, message: discord.Message, *members: Annotate.Member):
    """ Mute users. """
    success = yield from manage_mute(client, message, client.add_roles, *members)

    # Member was muted, success!
    if success:
        yield from client.say(message, "Muted {}".format(utils.format_members(*members)))


@plugins.command(usage="<users ...>")
@utils.permission("manage_messages")
def unmute(client: discord.Client, message: discord.Message, *members: Annotate.Member):
    """ Unmute users. """
    success = yield from manage_mute(client, message, client.remove_roles, *members)

    # Member was muted, success!
    if success:
        yield from client.say(message, "Unmuted {}".format(utils.format_members(*members)))


@plugins.command(usage="<users ...> <minutes>")
@utils.permission("manage_messages")
def timeout(client: discord.Client, message: discord.Message, *members: Annotate.Member, minutes: int):
    """ Timeout users for given minutes. """
    success = yield from manage_mute(client, message, client.add_roles, *members)

    # Do not progress if the member was not successfully muted
    # At this point, manage_mute will have reported any errors
    if not success:
        return

    yield from client.say(message, "Timed out {} for `{}` minutes.".format(utils.format_members(*members), minutes))

    # Sleep for the given minutes and unmute the member
    yield from asyncio.sleep(minutes * 60)  # Since asyncio.sleep takes seconds, multiply by 60
    yield from manage_mute(client, message, client.remove_roles, *members)


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
