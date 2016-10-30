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
client = plugins.client  # type: discord.Client


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
async def moderate_(message, _: utils.placeholder):
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
    async def display_setting(message: discord.Message):
        """ The command to display the current setting. """
        setup_default_config(message.server)
        current = moderate.data[message.server.id][name]
        await client.say(message, "{} is **{}**.".format(setting, "enabled" if current else "disabled"))

    @display_setting.command(hidden=True, aliases="true set enable")
    @utils.permission(*permissions)
    async def on(message: discord.Message):
        """ The command to enable this setting. """
        moderate.data[message.server.id][name] = True
        moderate.save()
        await client.say(message, "{} **enabled**.".format(setting))

    @display_setting.command(hidden=True, aliases="false unset disable")
    @utils.permission(*permissions)
    async def off(message: discord.Message):
        """ The command to enable this setting. """
        moderate.data[message.server.id][name] = False
        moderate.save()
        await client.say(message, "{} **disabled**.".format(setting))


add_setting("NSFW filter", permissions=["manage_server"])
add_setting("Changelog", permissions=["manage_server"], default=False)


async def manage_mute(message: discord.Message, function, *members: discord.Member):
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
            await client.say(message, "I refuse to mute myself!")
            continue

        while True:
            try:
                await function(member, muted_role)
            except discord.errors.Forbidden:
                await client.say(message, "I do not have permission to give members the `Muted` role.")
                return None
            except discord.errors.HTTPException:
                continue
            else:
                muted_members.append(member)
                break

    return muted_members or None


@plugins.command(pos_check=True)
@utils.permission("manage_messages")
async def mute(message: discord.Message, *members: Annotate.Member):
    """ Mute the specified members. """
    muted_members = await manage_mute(message, client.add_roles, *members)

    # Some members were muted, success!
    if muted_members:
        await client.say(message, "Muted {}".format(utils.format_objects(*muted_members, dec="`")))


@plugins.command(pos_check=True)
@utils.permission("manage_messages")
async def unmute(message: discord.Message, *members: Annotate.Member):
    """ Unmute the specified members. """
    muted_members = await manage_mute(message, client.remove_roles, *members)

    # Some members were unmuted, success!
    if muted_members:
        await client.say(message, "Unmuted {}".format(utils.format_objects(*muted_members, dec="`")))


@plugins.command()
@utils.permission("manage_messages")
async def timeout(message: discord.Message, member: Annotate.Member, minutes: float, reason: Annotate.Content):
    """ Timeout a user in minutes (will accept decimal numbers), send them
    the reason for being timed out and post the reason in the server's
    changelog if it has one. """
    client.loop.create_task(client.delete_message(message))
    muted_members = await manage_mute(message, client.add_roles, member)

    # Do not progress if the members were not successfully muted
    # At this point, manage_mute will have reported any errors
    if not muted_members:
        return

    changelog_channel = get_changelog_channel(message.server)

    # Tell the member and post in the changelog
    m = "You were timed out from **{}** for **{} minutes**. \n**Reason:** {}".format(message.server, minutes, reason)
    await client.send_message(member, m)

    if changelog_channel:
        await client.send_message(changelog_channel, "{} Timed out {} for **{} minutes**. **Reason:** {}".format(
            message.author.mention, member.mention, minutes, reason
        ))

    # Sleep for the given hours and unmute the member
    await asyncio.sleep(minutes * 60)  # Since asyncio.sleep takes seconds, multiply by 60^2
    await manage_mute(message, client.remove_roles, *muted_members)


@plugins.command()
@utils.permission("manage_messages")
async def purge(message: discord.Message, num: utils.int_range(1, 100),
                *members: Annotate.Member):
    """ Purge the given amount of messages from the specified members or all.
    `num` is a number from 1 to 100. """
    to_delete = []

    async for m in client.logs_from(message.channel, limit=100, before=message):
        if len(to_delete) >= num:
            break

        if not members or m.author in members:
            to_delete.append(m)

    deleted = len(to_delete)
    if deleted > 1:
        await client.delete_messages(to_delete)
    elif deleted == 1:
        await client.delete_message(to_delete[0])
    
    await client.say(message, "Purged **{}** message{}.".format(deleted, "" if deleted == 1 else "s"))


async def check_nsfw(message: discord.Message):
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
            await client.delete_message(message)

        nsfw_channel = discord.utils.find(lambda c: "nsfw" in c.name, message.server.channels)

        if nsfw_channel:
            await client.say(message, "{0.mention}: **Please post NSFW content in {1.mention}**".format(
                message.author, nsfw_channel))

        return True


@plugins.event()
async def on_message(message: discord.Message):
    """ Check plugin settings. """
    # Do not check in private messages
    if message.channel.is_private:
        return False

    setup_default_config(message.server)

    nsfw_success = await check_nsfw(message)
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
async def on_message_delete(message: discord.Message):
    """ Update the changelog with deleted messages. """
    changelog_channel = get_changelog_channel(message.server)

    # Don't log any message the bot deleted
    for m in client.last_deleted_messages:
        if m.id == message.id:
            return

    if not changelog_channel:
        return

    if message.channel == changelog_channel:
        return

    if message.author == client.user:
        return

    await client.send_message(
        changelog_channel,
        "{0.author.mention}'s message was deleted in {0.channel.mention}:\n{0.clean_content}".format(message)
    )


@plugins.event()
async def on_channel_create(channel: discord.Channel):
    """ Update the changelog with created channels. """
    if channel.is_private:
        return

    changelog_channel = get_changelog_channel(channel.server)
    if not changelog_channel:
        return

    # Differ between voice channels and text channels
    if channel.type == discord.ChannelType.text:
        await client.send_message(changelog_channel, "Channel {0.mention} was created.".format(channel))
    else:
        await client.send_message(changelog_channel, "Voice channel **{0.name}** was created.".format(channel))


@plugins.event()
async def on_channel_delete(channel: discord.Channel):
    """ Update the changelog with deleted channels. """
    if channel.is_private:
        return

    changelog_channel = get_changelog_channel(channel.server)
    if not changelog_channel:
        return

    # Differ between voice channels and text channels
    if channel.type == discord.ChannelType.text:
        await client.send_message(changelog_channel, "Channel **#{0.name}** was deleted.".format(channel))
    else:
        await client.send_message(changelog_channel, "Voice channel **{0.name}** was deleted.".format(channel))


@plugins.event()
async def on_channel_update(before: discord.Channel, after: discord.Channel):
    """ Update the changelog when a channel changes name. """
    if after.is_private:
        return

    changelog_channel = get_changelog_channel(after.server)
    if not changelog_channel:
        return

    # We only want to update when a name change is performed
    if before.name == after.name:
        return

    # Differ between voice channels and text channels
    if after.type == discord.ChannelType.text:
        await client.send_message(
            changelog_channel, "Channel **#{0.name}** changed name to {1.mention}, **{1.name}**.".format(before, after))
    else:
        await client.send_message(
            changelog_channel, "Voice channel **{0.name}** changed name to **{1.name}**.".format(before, after))


@plugins.event()
async def on_member_join(member: discord.Member):
    """ Update the changelog with members joined. """
    changelog_channel = get_changelog_channel(member.server)
    if not changelog_channel:
        return

    await client.send_message(changelog_channel, "{0.mention} joined the server.".format(member))


@plugins.event()
async def on_member_remove(member: discord.Member):
    """ Update the changelog with deleted channels. """
    changelog_channel = get_changelog_channel(member.server)
    if not changelog_channel:
        return

    await client.send_message(changelog_channel, "{0.mention} ({0.name}) left the server.".format(member))


@plugins.event()
async def on_member_update(before: discord.Member, after: discord.Member):
    """ Update the changelog with any changed names and roles. """
    name_change = not before.name == after.name
    nick_change = not before.nick == after.nick
    role_change = not before.roles == after.roles

    changelog_channel = get_changelog_channel(after.server)
    if not changelog_channel:
        return

    # Format the nickname or username changed
    if name_change:
        m = "{0.mention} (previously **{0.name}**) changed their username to **{1.name}**."
    elif nick_change:
        if not before.nick:
            m = "{0.mention} got the nickname **{1.nick}**."
        elif not after.nick:
            m = "{0.mention} (previously **{0.nick}**) no longer has a nickname."
        else:
            m = "{0.mention} (previously **{0.nick}**) got the nickname **{1.nick}**."
    elif role_change:
        muted_role = discord.utils.get(after.server.roles, name="Muted")

        if len(before.roles) > len(after.roles):
            role = [r for r in before.roles if r not in after.roles][0]
            if role == muted_role:
                return

            m = "{0.mention} lost the role **{1.name}**".format(after, role)
        else:
            role = [r for r in after.roles if r not in before.roles][0]
            if role == muted_role:
                return

            m = "{0.mention} received the role **{1.name}**".format(after, role)
    else:
        return

    if name_change or nick_change:
        await client.send_message(changelog_channel, m.format(before, after))
    else:
        await client.send_message(changelog_channel, m)


@plugins.event()
async def on_member_ban(member: discord.Member):
    """ Update the changelog with banned members. """
    changelog_channel = get_changelog_channel(member.server)
    if not changelog_channel:
        return

    await client.send_message(changelog_channel,
                                   "{0.mention} ({0.name}) was banned from the server.".format(member))


@plugins.event()
async def on_member_unban(member: discord.Member):
    """ Update the changelog with unbanned members. """
    changelog_channel = get_changelog_channel(member.server)
    if not changelog_channel:
        return

    await client.send_message(changelog_channel, "{0.mention} was unbanned from the server.".format(member))
