""" Plugin for playing music.

Some of the logic is very similar to the example at:
    https://github.com/Rapptz/discord.py/blob/master/examples/playlist.py

Commands:
    music
"""

from collections import namedtuple, deque
from typing import Dict

import asyncio
import discord

import plugins
from pcbot import utils, Annotate, Config
client = plugins.client  # type: discord.Client

music_channels = Config("music_channels", data=[])
voice_states = {}  # type: Dict[discord.Server, VoiceState]
youtube_dl_options = dict(
    default_search="auto",
    quiet=True,
    nocheckcertificate=True
)

max_songs_queued = 2  # How many songs each member are allowed in the queue at once
max_song_length = 60 * 37  # The maximum song length in seconds
default_volume = .6

if not discord.opus.is_loaded():
    discord.opus.load_opus('libopus-0.x64.dll')


Song = namedtuple("Song", "channel player requester")


def format_song(song: Song, url=True):
    """ Format a song request. """
    # The player duration is given in seconds; convert it to h:mm
    duration = ""
    if song.player.duration:
        duration = " / **{0}:{1:02}**".format(*divmod(int(song.player.duration), 60))

    return "**{0.title}** requested by **{1.display_name}**{2}".format(song.player, song.requester, duration) \
           + ("\n**URL**: <{0.url}>".format(song.player) if url else "")


class VoiceState:
    def __init__(self, voice):
        self.voice = voice
        self.current = None
        self._volume = default_volume
        self.queue = deque()  # The queue contains items of type Song
        self.skip_votes = set()

    def is_playing(self):
        """ Check if the bot is playing music. """
        if self.current:
            return not self.current.player.is_done()

        return False

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value: float):
        if value > 1:
            value = 1
        elif value < .01:
            value = default_volume

        self._volume = value
        if self.is_playing():
            self.current.player.volume = value

    def format_playing(self):
        if self.is_playing():
            return format_song(self.current)
        else:
            return "*Nothing.*"

    def play_next(self):
        """ Play the next song if there are any. """
        self.skip_votes.clear()
        if not self.queue:
            return

        self.current = self.queue.popleft()
        self.current.player.start()

    def skip(self):
        """ Skip the song currently playing. """
        if self.is_playing():
            self.current.player.stop()


@plugins.command(aliases="m", disabled_pm=True)
async def music(message, _: utils.placeholder):
    """ Manage music. If a music channel is assigned, the bot will join
    whenever someone joins it. """
    pass


def get_server_channel(server: discord.Server):
    """ Return the server's music channel or None. """
    for channel in server.channels:
        if channel.id in music_channels.data:
            return channel

    return None


def client_connected(server: discord.Server):
    """ Returns True or False whether the bot is client_connected to the
    Music channel in this server. """
    channel = get_server_channel(server)
    return server.me.voice_channel == channel and server in voice_states


def assert_connected(member: discord.Member):
    """ Throws an AssertionError exception when neither the bot nor
    the member is connected to the music channel."""
    channel = get_server_channel(member.server)

    assert member.voice.voice_channel == channel, "**You are not connected to the voice channel.**"
    assert client_connected(member.server), "**The bot is not connected to the voice channel.**"


@music.command(aliases="p pl")
async def play(message: discord.Message, song: Annotate.CleanContent):
    """ Play a song. The given song could either be a URL or keywords
    to lookup videos in youtube. """
    assert_connected(message.author)
    state = voice_states[message.server]

    # Check that the member hasn't already requested enough songs
    songs_queued = sum(1 for s in state.queue if s.requester == message.author)
    assert songs_queued < max_songs_queued, "**You have queued enough songs for now.**"

    # Strip any embed characters, spaces or code symbols.
    song = song.strip("< >`")

    try:
        player = await state.voice.create_ytdl_player(song, ytdl_options=youtube_dl_options, after=state.play_next)
    except:
        await client.say(message, "**Could not add this song to the queue.**")
        return

    # Make sure the song isn't too long
    if player.duration:
        assert player.duration < max_song_length, "**The requested song is too long.**"

    player.volume = state.volume
    song = Song(player=player, requester=message.author, channel=message.channel)
    await client.send_message(song.channel, "Queued: " + format_song(song))
    state.queue.append(song)

    # Start the song when there are none
    if not state.is_playing():
        state.play_next()


@music.command(aliases="s next")
async def skip(message: discord.Message):
    """ Skip the song currently playing. """
    assert_connected(message.author)
    state = voice_states[message.server]
    assert state.is_playing(), "**There is no song currently playing.**"
    assert message.author not in state.skip_votes, "**You have already voted to skip this song.**"

    # We want to skip immediately when the requester skips their own song.
    if message.author == state.current.requester:
        await client.say(message, "**Skipped song on behalf of the requester.**")
        state.skip()
        return

    state.skip_votes.add(message.author)

    # In order to skip, everyone but the requester and the bot must vote
    needed_to_skip = len(get_server_channel(message.server).voice_members) - 2
    votes = len(state.skip_votes)
    if votes >= needed_to_skip:
        await client.say(message, "**Skipped song.**")
        state.skip()
    else:
        await client.say(message, "**Voted to skip the current song.** `{}/{}`".format(votes, needed_to_skip))


@music.command(aliases="volume v")
async def vol(message: discord.Message, volume: int):
    """ Set the volume of the player. Volume should be a number in percent. """
    assert_connected(message.author)
    state = voice_states[message.server]
    state.volume = volume / 100
    await client.say(message, "Set the volume to **{:.00%}**.".format(state.volume))


@music.command(aliases="np")
async def playing(message: discord.Message):
    """ Return the name and URL of the song currently playing. """
    assert_connected(message.author)
    state = voice_states[message.server]
    await client.say(message, "Playing: " + state.format_playing())


@music.command(aliases="q list l")
async def queue(message: discord.Message):
    """ Return a list of the queued songs. """
    assert_connected(message.author)
    state = voice_states[message.server]
    assert state.queue, "**There are no songs queued.**"

    msg = await client.say(message, "```elm\n{}```".format(
        "\n".join(format_song(s, url=False).replace("**", "") for s in state.queue)))
    await asyncio.sleep(20)
    await client.delete_message(msg)


@music.command()
@utils.owner
async def link(message: discord.Message, channel: Annotate.Channel):
    """ Link the Music bot to a channel in a server. """
    assert channel.type is discord.ChannelType.voice, "**The given channel is not a voice channel.**"
    assert channel.id not in music_channels.data, "**This voice channel is already linked.**"
    assert get_server_channel(message.server) is None, "**A voice channel is already linked to this server.**"

    # Link the channel
    music_channels.data.append(channel.id)
    music_channels.save()
    await client.say(message, "Voice channel **{0.name}** is now the music channel.".format(channel))


@music.command()
@utils.owner
async def unlink(message: discord.Message):
    """ Unlink this server's music channel. """
    channel = get_server_channel(message.server)
    assert channel, "**This server has no voice channel linked.**"

    # Unlink the channel
    music_channels.data.remove(channel.id)
    music_channels.save()
    await client.say(message, "This server no longer has a music channel.")


@plugins.event()
async def on_voice_state_update(before: discord.Member, after: discord.Member):
    """ Handle joining and leaving channels. The bot will automatically
    join the server's voice channel when a member joins. """
    server = before.server
    channel = get_server_channel(server)
    if channel is None:
        return

    # Leave the voice channel we're client_connected to when the only one here is the bot
    if server in voice_states and server.me.voice_channel == channel:
        if len(channel.voice_members) == 1:
            state = voice_states[server]
            await state.voice.disconnect()
            if state.is_playing():
                state.queue.clear()
                state.skip()
            del voice_states[server]

    # Connect to the voice channel when there are people in it but not us
    else:
        if len(channel.voice_members) >= 1 and not server.me.voice_channel == channel:
            try:
                voice = await client.join_voice_channel(channel)
            except discord.errors.ClientException:
                # The bot is in another channel, so we'll get the voice client and move the bot
                voice = client.voice_client_in(server)
                await voice.move_to(channel)
            voice_states[server] = VoiceState(voice)
