""" osu! commands

This plugin currently only assigns osu! profiles and notifies the server whenever they set a new top score (pp best).
The notifying is a near identical copy of plugins/twitch.py

Commands:
!osu
"""

import logging

import discord
import asyncio
import aiohttp

from pcbot import Config
from pcbot import download_file

commands = {
    "osu": {
        "usage": "!osu <option>\n"
                 "Options:\n"
                 "     set <username>\n"
                 "     get\n"
                 "     notify-channel [channel]\n",
        "desc": "Handle osu! commands.\n"
                "`set` assigns your osu! user for notifying.\n"
                "`get` returns an osu! userpage link..\n"
                "~~`notify-channel` sets a channel as the notify channel. This channel should not be used by any "
                "member. Specify no channel to disable. **Requires `Manage Server` permission.**~~"
    }
}

osu = Config("osu", data={"key": "change to your api key", "profiles": {}})
osu_tracking = {}  # Saves the requested data or deletes whenever the user stops playing (for comparisons)
update_interval = 30  # Seconds
logging_interval = 30  # Minutes

request_limit = 100

osu_api = "https://osu.ppy.sh/api/"

logging.getLogger("requests").setLevel(logging.WARNING)


def format_new_score(member: discord.Member, score: dict):
    """ Format any score set by the member. """
    sign = "-"
    if score["perfect"]:
        sign = "+"

    return """
    {member.mention} set a new best on https://osu.ppy.sh/b/{beatmap_id}
    **{pp}pp, {rank}**
    ```diff
     300s    100s    50s     miss    combo
    {sign}{count300:<8}{count100:<8}{count50:<8}{countmiss:<8}{maxcombo:<8}
    ```
    **Profile**: https://osu.ppy.sh/u/{user_id}
    """.format(member=member, sign=sign, **score)


def updates_per_log():
    """ Returns the amount of updates needed before logging interval is met. """
    return logging_interval // (update_interval / 60)


def get_beatmaps(**params):
    """ Returns a list of beatmaps specified by lookup.

    Request_params is any parameter accepted by the osu! API.
    """
    params["k"] = osu.data["key"]

    with aiohttp.ClientSession() as session:
        response = yield from session.get(osu_api + "get_beatmaps", params=params)
        beatmaps = yield from response.json() if response.status == 200 else []

    return beatmaps


def get_beatmap(beatmaps, **lookup):
    """ Finds and returns the first beatmap with the lookup specified.

    Beatmaps is a list of beatmaps and could be used with get_beatmaps()
    Lookup is any key stored in a beatmap from get_beatmaps()
    """
    if not beatmaps:
        return None

    matched_beatmap = None

    for beatmap in beatmaps:
        match = True
        for key, value in lookup.items():
            if key.lower() not in beatmap:
                raise KeyError("The list of beatmaps does not have key: {}".format(key))

            if not beatmap[key].lower() == value.lower():
                match = False

        if match:
            matched_beatmap = beatmap
            break

    return matched_beatmap


@asyncio.coroutine
def on_ready(client: discord.Client):
    global osu_tracking

    if osu.data["key"] == "change to your api key":
        logging.warning("osu! functionality is unavailable until an API key is provided")

    sent_requests = 0
    updated = 0

    while not client.is_closed:
        try:
            yield from asyncio.sleep(update_interval)

            # Go through all set channels playing osu! and update their status
            for member_id, profile in osu.data["profiles"].items():
                def check_playing(m):
                    if m.id == member_id and m.game:
                        if m.game.name.startswith("osu!"):
                            return True

                    return False

                member = discord.utils.find(check_playing, client.get_all_members())

                if member:
                    sent_requests += 1

                    params = {
                        "k": osu.data["key"],
                        "u": profile,
                        "type": "id",
                        "limit": request_limit
                    }

                    with aiohttp.ClientSession() as session:
                        response = yield from session.get(osu_api + "get_user_best", params=params)

                        scores = yield from response.json() if response.status == 200 else []

                    if scores:
                        # Go through all scores and see if they've already been tracked
                        if member_id in osu_tracking:
                            new_score = None

                            for score in scores:
                                if score not in osu_tracking[member_id]:
                                    new_score = score

                            # Tell all mutual servers if this user set a nice play
                            if new_score:
                                for server in client.servers:
                                    if member in server.members:
                                        yield from client.send_message(
                                            server,
                                            format_new_score(member=member, score=new_score)
                                        )

                        osu_tracking[member_id] = list(scores)

            # Send info on how many requests were sent the last 30 minutes (60 loops)
            updated += 1

            if updated % updates_per_log() == 0:
                logging.info("Requested osu! scores {} times in {} minutes.".format(sent_requests, logging_interval))
                sent_requests = 0

        except Exception as e:
            logging.info("Error: " + str(e))


@asyncio.coroutine
def on_command(client: discord.Client, message: discord.Message, args: list):
    if args[0] == "!osu":
        m = "Please see `!help osu`."
        if len(args) > 1:
            # Assign an osu! profile to your name or remove it
            if args[1] == "set":
                if len(args) > 2:
                    profile = " ".join(args[2:])

                    params = {
                        "k": osu.data["key"],
                        "u": profile
                    }

                    with aiohttp.ClientSession() as session:
                        response = yield from session.get(osu_api + "get_user", params=params)

                        user = yield from response.json() if response.status == 200 else []

                    if user:
                        # Clear the scores when changing user
                        if message.author.id in osu_tracking:
                            osu_tracking.pop(message.author.id)

                        osu.data["profiles"][message.author.id] = user[0]["user_id"]
                        osu.save()
                        m = "Set your osu! profile to `{}`.".format(user[0]["username"])
                    else:
                        m = "User {} does not exist.".format(profile)
                else:
                    if message.author.id in osu.data["profiles"]:
                        osu.data["profiles"].pop(message.author.id)
                        osu.save()
                        m = "osu! profile unlinked."

            # Return the member's or another member's osu! profile as a link and upload a signature
            elif args[1] == "get":
                if len(args) > 2:
                    member = client.find_member(message.server, " ".join(args[2:]))
                else:
                    member = message.author

                if member:
                    if member.id in osu.data["profiles"]:
                        user_id = osu.data["profiles"][member.id]

                        # Set the signature color to that of the role color
                        color = "pink"

                        if len(member.roles) > 1:
                            color = "hex{0:02x}{1:02x}{2:02x}".format(*member.roles[1].colour.to_tuple())

                        # Download and upload the signature
                        params = {
                            "colour": color,
                            "uname": user_id,
                            "pp": 1,
                            "countryrank": True,
                            "xpbar": True
                        }

                        signature = yield from download_file("http://lemmmy.pw/osusig/sig.php", **params)

                        yield from client.send_file(message.channel, signature, filename="sig.png")
                        m = "https://osu.ppy.sh/u/{}".format(user_id)
                    else:
                        m = "No osu! profile assigned to {}!".format(member.name)
                else:
                    m = "Found no such member."

            # # Set or get the osu! notify channel
            # elif args[1] == "notify-channel":
            #     if message.author.permissions_in(message.channel).manage_server:
            #         if len(args) > 2:
            #             channel = client.find_channel(message.server, args[2])
            #
            #             if channel:
            #                 osu.data["notify-channel"][message.server.id] = channel.id
            #                 osu.save()
            #                 m = "Notify channel set to {}.".format(channel.mention)
            #         else:
            #             if "notify-channel" in osu.data:
            #                 twitch_channel = client.get_channel(osu.data["notify-channel"])
            #                 if twitch_channel:
            #                     m = "Twitch notify channel is {}.".format(twitch_channel)
            #                 else:
            #                     m = "The twitch notify channel no longer exists!"
            #             else:
            #                 m = "A twitch notify channel has not been set."
            #     else:
            #         m = "You need `Manage Server` to use this command."

        yield from client.send_message(message.channel, m)
