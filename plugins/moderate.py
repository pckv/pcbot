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
    if not all(k in moderate.data[server.id].keys() for k in default_config):
        moderate.data[server.id] = default_config
        moderate.save()


@plugins.command(name="moderate")
def moderate_(client, message, _: utils.placeholder):
    """ Change moderation settings. """
    pass


def add_setting(setting: str, default=True, name=None, permissions=None):
    """ Create a set of subcommands for the given setting (True or False).

    :param setting: display name for the setting.
    :param default: The default value for this setting.
    :param name: optionally set the name of the subcommand.
    :param permissions: what permissions are required to change this setting (list of str). """
    if not name:
        name = setting.lower().replace("\n", "").replace(" ", "")

    default_config[name] = default

    @moderate_.command(name=name,
                       description="Display current {} setting or enable/disable it.".format(setting),
                       usage="[on | off]")
    def display_setting(client: discord.Client, message: discord.Message):
        """ The command to display the current setting. """
        setup_default_config(message.server)
        current = moderate.data[message.server.id][name]
        yield from client.say(message, "{} is **{}**.".format(setting, "enabled" if current else "disabled"))

    @display_setting.command(hidden=True, aliases="true set enable")
    @utils.permission(*permissions)
    def on(client: discord.Client, message: discord.Message):
        """ The command to enable this setting. """
        moderate.data[message.server.id][name] = True
        moderate.save()
        yield from client.say(message, "{} **enabled**.".format(setting))

    @display_setting.command(hidden=True, aliases="false unset disable")
    @utils.permission(*permissions)
    def off(client: discord.Client, message: discord.Message):
        """ The command to enable this setting. """
        moderate.data[message.server.id][name] = False
        moderate.save()
        yield from client.say(message, "{} **disabled**.".format(setting))


add_setting("NSFW filter", permissions=["manage_server"])
add_setting("Changelog", permissions=["manage_server"], default=False)


@asyncio.coroutine
def manage_mute(client: discord.Client, message: discord.Message, *members: discord.Member, muted=True):
    """ Add or remove Muted role for given members.

    :param function: either client.add_roles or client.remove_roles
    :return: list of muted/unmuted members or None """
    # Manage Roles is required to add or remove the Muted role
    assert message.server.me.permissions_in(message.channel).manage_roles, \
        "I need `Manage Roles` permission to use this command."

    muted_role = discord.utils.get(message.server.roles, name="Muted")
    function = client.add_roles if muted else client.remove_roles

    # The server needs to properly manage the Muted role
    assert muted_role, "No role assigned for muting. Please create a `Muted` role."

    muted_members = []

    # Try giving members the Muted role
    for member in members:
        if member is message.server.me:
            yield from client.say(message, "I refuse to {}mute myself!".format("" if mute else "un"))
            continue

        while True:
            try:
                yield from function(member, muted_role)
                yield from client.server_voice_state(member, mute=muted)
            except discord.errors.Forbidden:
                yield from client.say(message, "I either don't have permission to give members the `Muted` role, or "
                                               "lack the `Mute Members` voice role.")
                return None
            except discord.errors.HTTPException:
                continue
            else:
                muted_members.append(member)
                break

    return muted_members or None


@plugins.command(pos_check=True)
@utils.permission("manage_messages")
def mute(client: discord.Client, message: discord.Message, *members: Annotate.Member):
    """ Mute the specified members. """
    muted_members = yield from manage_mute(client, message, *members, mute=True)

    # Some members were muted, success!
    if muted_members:
        yield from client.say(message, "Muted {}".format(utils.format_objects(*muted_members, dec="`")))


@plugins.command(pos_check=True)
@utils.permission("manage_messages")
def unmute(client: discord.Client, message: discord.Message, *members: Annotate.Member):
    """ Unmute the specified members. """
    muted_members = yield from manage_mute(client, message, *members, mute=False)

    # Some members were unmuted, success!
    if muted_members:
        yield from client.say(message, "Unmuted {}".format(utils.format_objects(*muted_members, dec="`")))


@plugins.command(pos_check=True)
@utils.permission("manage_messages")
def timeout(client: discord.Client, message: discord.Message, *members: Annotate.Member, minutes: int):
    """ Timeout the specified members for given minutes. """
    muted_members = yield from manage_mute(client, message, *members, mute=True)

    # Do not progress if the members were not successfully muted
    # At this point, manage_mute will have reported any errors
    if not muted_members:
        return

    yield from client.say(message, "Timed out {} for `{}` minutes.".format(
        utils.format_objects(*muted_members, dec="`"), minutes))

    # Sleep for the given minutes and unmute the member
    yield from asyncio.sleep(minutes * 60)  # Since asyncio.sleep takes seconds, multiply by 60
    yield from manage_mute(client, message, *muted_members, mute=False)


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


@plugins.event()
def on_message(client: discord.Client, message: discord.Message):
    """ Check plugin settings. """
    # Do not check in private messages
    if message.channel.is_private:
        return False

    setup_default_config(message.server)

    nsfw_success = yield from check_nsfw(client, message)
    if nsfw_success is True:
        return True


def get_changelog_channel(server: discord.Server):
    """ Return the changelog channel for a server. """
    setup_default_config(server)
    if not moderate.data[server.id]["changelog"]:
        return

    channel = discord.utils.get(server.channels, name="changelog")
    if not channel:
        return

    permissions = channel.permissions_for(server.me)
    if not permissions.send_messages or not permissions.read_messages:
        return

    return channel


@plugins.event()
def on_message_delete(client: discord.Client, message: discord.Message):
    """ Update the changelog with deleted messages. """
    changelog_channel = get_changelog_channel(message.server)
    if not changelog_channel:
        return

    if message.channel == changelog_channel:
        return

    if message.author == client.user:
        return

    if message.content.startswith("|"):  # Custom check for pastas
        return

    yield from client.send_message(
        changelog_channel,
        "{0.author.mention}'s message was deleted in {0.channel.mention}:\n{0.clean_content}".format(message)
    )


@plugins.event()
def on_channel_create(client: discord.Client, channel: discord.Channel):
    """ Update the changelog with created channels. """
    if channel.is_private:
        return

    changelog_channel = get_changelog_channel(channel.server)
    if not changelog_channel:
        return

    # Differ between voice channels and text channels
    if channel.type == discord.ChannelType.text:
        yield from client.send_message(changelog_channel, "Channel {0.mention} was created.".format(channel))
    else:
        yield from client.send_message(changelog_channel, "Voice channel **{0.name}** was created.".format(channel))


@plugins.event()
def on_channel_delete(client: discord.Client, channel: discord.Channel):
    """ Update the changelog with deleted channels. """
    if channel.is_private:
        return

    changelog_channel = get_changelog_channel(channel.server)
    if not changelog_channel:
        return

    # Differ between voice channels and text channels
    if channel.type == discord.ChannelType.text:
        yield from client.send_message(changelog_channel, "Channel #{0.name} was deleted.".format(channel))
    else:
        yield from client.send_message(changelog_channel, "Voice channel **{0.name}** was deleted.".format(channel))


@plugins.event()
def on_member_join(client: discord.Client, member: discord.Member):
    """ Update the changelog with members joined. """
    changelog_channel = get_changelog_channel(member.server)
    if not changelog_channel:
        return

    yield from client.send_message(changelog_channel, "{0.mention} joined the server.".format(member))


@plugins.event()
def on_member_remove(client: discord.Client, member: discord.Member):
    """ Update the changelog with deleted channels. """
    changelog_channel = get_changelog_channel(member.server)
    if not changelog_channel:
        return

    yield from client.send_message(changelog_channel, "{0.mention} ({0.name}) left the server.".format(member))


@plugins.event()
def on_member_update(client: discord.Client, before: discord.Member, after: discord.Member):
    """ Update the changelog with any changed names. """
    name_change = not before.name == after.name
    nick_change = not before.nick == after.nick

    if not name_change and not nick_change:
        return

    changelog_channel = get_changelog_channel(after.server)
    if not changelog_channel:
        return

    # Format the nickname or username changed
    if name_change:
        m = "{0.mention} (previously **{0.name}**) changed their username to **{1.name}**."
    else:
        if not before.nick:
            m = "{0.mention} got the nickname **{1.nick}**."
        elif not after.nick:
            m = "{0.mention} (previously **{0.nick}**), no longer has a nickname."
        else:
            m = "{0.mention} (previously **{0.nick}**) got the nickname **{1.nick}**."

    yield from client.send_message(changelog_channel, m.format(before, after))


@plugins.event()
def on_member_ban(client: discord.Client, member: discord.Member):
    """ Update the changelog with banned members. """
    changelog_channel = get_changelog_channel(member.server)
    if not changelog_channel:
        return

    yield from client.send_message(changelog_channel,
                                   "{0.mention} ({0.name}) was banned from the server.".format(member))


@plugins.event()
def on_member_unban(client: discord.Client, member: discord.Member):
    """ Update the changelog with unbanned members. """
    changelog_channel = get_changelog_channel(member.server)
    if not changelog_channel:
        return

    yield from client.send_message(changelog_channel, "{0.mention} was unbanned from the server.".format(member))
