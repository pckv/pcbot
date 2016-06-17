""" Plugin for server moderation

The bot will perform different tasks when some settings are enabled in a server:

_____________________________________NSFW Filter_____________________________________
    If enabled on the server, spots any text containing the keyword nsfw and a link.
    Then tries to delete their message, and post a link to the dedicated nsfw channel.

Commands:
    moderate
    mute
    unmute
    timeout
"""

from collections import defaultdict

import discord
import asyncio

from pcbot import Config, utils, Annotate
import plugins

moderate = Config("moderate", data=defaultdict(dict))
default_config = {}  # Used by add_setting helper function


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


def add_setting(setting: str, default=True, name=None, permissions=None):
    """ Create a set of subcommands for the given setting (True or False).

    :param setting: display name for the setting.
    :param default: The default value for this setting.
    :param name: optionally set the name of the subcommand.
    :param permissions: what permissions are required to change this setting (list of str). """
    if not name:
        name = setting.lower().replace("\n", "").replace(" ", "")

    default_config[name] = default

    @moderate_.command(name=name, description="Display current {} setting.".format(setting))
    def display(client: discord.Client, message: discord.Message):
        """ The command to display the current setting. """
        setup_default_config(message.server)
        current = moderate.data[message.server.id][name]
        yield from client.say(message, "{} is `{}`.".format(setting, "ON" if current else "OFF"))

    @display.command(name="on")
    @utils.permission(*permissions)
    def enable_setting(client: discord.Client, message: discord.Message):
        """ The command to enable this setting. """
        moderate.data[message.server.id][name] = True
        moderate.save()
        yield from client.say(message, "{} enabled.".format(setting))

    @display.command(name="off")
    @utils.permission(*permissions)
    def enable_setting(client: discord.Client, message: discord.Message):
        """ The command to enable this setting. """
        moderate.data[message.server.id][name] = False
        moderate.save()
        yield from client.say(message, "{} disabled.".format(setting))


add_setting("NSFW filter", permissions=["manage_server"])


@asyncio.coroutine
def manage_mute(client: discord.Client, message: discord.Message, function, *members: discord.Member):
    """ Add or remove Muted role for given members.

    :param function: either client.add_roles or client.remove_roles
    :return: list of muted/unmuted members or None """
    # Manage Roles is required to add or remove the Muted role
    assert message.server.me.permissions_in(message.channel).manage_roles, \
        "I need `Manage Roles` permission to use this command."

    muted_role = discord.utils.get(message.server.roles, name="Muted")

    # The server needs to properly manage the Muted role
    assert muted_role, "No role assigned for muting. Please create a `Muted` role."

    muted_members = []

    # Try giving members the Muted role
    for member in members:
        if member is message.server.me:
            yield from client.say(message, "I refuse to mute myself!")
            continue

        while True:
            try:
                yield from function(member, muted_role)
            except discord.errors.Forbidden:
                yield from client.say(message, "I do not have permission to give members the `Muted` role.")
                return None
            except discord.errors.HTTPException:
                continue
            else:
                muted_members.append(member)
                break

    return muted_members or None


@plugins.command(usage="<users ...>", pos_check=True)
@utils.permission("manage_messages")
def mute(client: discord.Client, message: discord.Message, *members: Annotate.Member):
    """ Mute users. """
    # Since PCBOT handles positional arguments as optional, we have to check them manually
    assert members
    muted_members = yield from manage_mute(client, message, client.add_roles, *members)

    # Some members were muted, success!
    if muted_members:
        yield from client.say(message, "Muted {}".format(utils.format_members(*muted_members)))


@plugins.command(usage="<users ...>", pos_check=True)
@utils.permission("manage_messages")
def unmute(client: discord.Client, message: discord.Message, *members: Annotate.Member):
    """ Unmute users. """
    assert members
    muted_members = yield from manage_mute(client, message, client.remove_roles, *members)

    # Some members were unmuted, success!
    if muted_members:
        yield from client.say(message, "Unmuted {}".format(utils.format_members(*muted_members)))


@plugins.command(usage="<users ...> <minutes>", pos_check=True)
@utils.permission("manage_messages")
def timeout(client: discord.Client, message: discord.Message, *members: Annotate.Member, minutes: int):
    """ Timeout users for given minutes. """
    muted_members = yield from manage_mute(client, message, client.add_roles, *members)

    # Do not progress if the members were not successfully muted
    # At this point, manage_mute will have reported any errors
    if not muted_members:
        return

    yield from client.say(message, "Timed out {} for `{}` minutes.".format(utils.format_members(*muted_members),
                                                                           minutes))

    # Sleep for the given minutes and unmute the member
    yield from asyncio.sleep(minutes * 60)  # Since asyncio.sleep takes seconds, multiply by 60
    yield from manage_mute(client, message, client.remove_roles, *muted_members)


@asyncio.coroutine
def check_nsfw(client: discord.Client, message: discord.Message):
    """ Check if the message is NSFW (very rough check). """
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
            yield from client.say(message, "{0.mention}: **Please post NSFW content in {1.mention}**".format(
                message.author, nsfw_channel) )

        return True

    return False


@asyncio.coroutine
def on_message(client: discord.Client, message: discord.Message):
    """ Check plugin settings. """
    # Do not check in private messages
    if message.channel.is_private:
        return False

    setup_default_config(message.server)

    nsfw_success = yield from check_nsfw(client, message)
    if nsfw_success:
        return True

    return False
