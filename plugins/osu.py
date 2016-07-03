""" Plugin for osu! commands

This plugin will notify any registered user's pp difference and if they
set a new best also post that. Keep in mind this plugin might send a lot
of requests, so keep up to date with the "osu debug" command.

The "osu pp" command requires that you setup the "oppai" lib:
https://github.com/Francesco149/oppai

The directory would be "/plugins/osulib/oppai/". It should be setup so that
the bot can run "/plugins/osulib/oppai/oppai" as an executable.

Commands:
    osu
"""

import logging
from traceback import print_exc
import os
import platform
import re
from subprocess import Popen, PIPE

import discord
import asyncio

from pcbot import Config, utils, Annotate
import plugins
from plugins.osulib import api, Mods

osu_config = Config("osu", data=dict(key="change to your api key", profiles={}, mode={}))
osu_tracking = {}  # Saves the requested data or deletes whenever the user stops playing (for comparisons)
update_interval = 30  # Seconds
logging_interval = 30  # Minutes

pp_threshold = 0.1
score_request_limit = 100
member_timeout = 2  # How long to wait before removing a member from the register (update_interval * value seconds)

api.api_key = osu_config.data.get("key")
host = "https://osu.ppy.sh/"
oppai_path = "plugins/osulib/oppai/"  # Path to oppai lib for pp calculations
last_calc_beatmap = dict(beatmap_id="---", beatmapset_id="---")  # The last calculated beatmap info


def calculate_acc(mode: api.GameMode, score: dict):
    """ Calculate the accuracy using formulas from https://osu.ppy.sh/wiki/Accuracy """
    # Parse data from the score: 50s, 100s, 300s, misses, katu and geki
    c300, c100, c50 = int(score["count300"]), int(score["count100"]), int(score["count50"])
    miss, katu, geki = int(score["countmiss"]), int(score["countkatu"]), int(score["countgeki"])

    # CTB accuracy is done a tad bit differently, so we calculate that by itself
    if mode is api.GameMode.CTB:
        total_numbers_of_fruits_caught = c50 + c100 + c300
        total_numbers_of_fruits = miss + c50 + c100 + c300 + katu
        return total_numbers_of_fruits_caught / total_numbers_of_fruits

    total_points_of_hits, total_number_of_hits = 0, 0

    if mode is api.GameMode.Standard:
        total_points_of_hits = c50 * 50 + c100 * 100 + c300 * 300
        total_number_of_hits = miss + c50 + c100 + c300
    elif mode is api.GameMode.Taiko:
        total_points_of_hits = (miss * 0 + c100 * 0.5 + c300 * 1) * 300
        total_number_of_hits = miss + c100 + c300
    elif mode is api.GameMode.Mania:
        # In mania, katu is 200s and geki is MAXes
        total_points_of_hits = c50 * 50 + c100 * 100 + katu * 200 + (c300 + geki) * 300
        total_number_of_hits = miss + c50 + c100 + katu + c300 + geki

    return total_points_of_hits / (total_number_of_hits * 300)


def format_user_diff(mode: api.GameMode, pp: float, rank: int, country_rank: int, accuracy: float, iso: str, data: str):
    """ Get a bunch of differences and return a formatted string to send.
    iso is the country code. """
    formatted = "\u2139`{} {}pp {:+.2f}pp`".format(mode.name, data["pp_raw"], pp)
    formatted += (" \U0001f30d`#{:,}{}`".format(int(data["pp_rank"]),
                                                "" if int(rank) == 0 else " {:+}".format(int(rank))))
    formatted += (" :flag_{}:`#{:,}{}`".format(iso.lower(), int(data["pp_country_rank"]),
                                               "" if int(country_rank) == 0 else " {:+}".format(int(country_rank))))
    rounded_acc = round(accuracy, 3)
    if rounded_acc > 0:
        formatted += " \U0001f4c8"  # Graph with upwards trend
    elif rounded_acc < 0:
        formatted += " \U0001f4c9"  # Graph with downwards trend
    else:
        formatted += " \U0001f3af"  # Dart

    formatted += "`{:.3f}%".format(float(data["accuracy"]))
    if not rounded_acc == 0:
        formatted += " {:+}%`".format(rounded_acc)
    else:
        formatted += "`"

    return formatted


def format_new_score(mode: api.GameMode, score: dict, beatmap: dict, rank: int):
    """ Format any osu!Standard score. There should be a member name/mention in front of this string. """
    acc = calculate_acc(mode, score)
    return (
        "set a new best (`#{pos}/{limit}`) on *{artist} - {title}* **[{version}] {stars:.2f}\u2605**\n"
        "**{pp}pp, {rank} {scoreboard_rank}+{mods}**"
        "```diff\n"
        "  acc     300s    100s    50s     miss    combo\n"
        "{sign} {acc:<8.2%}{count300:<8}{count100:<8}{count50:<8}{countmiss:<8}{maxcombo}{max_combo}```"
        "**Profile**: <https://osu.ppy.sh/u/{user_id}>.\n"
        "**Beatmap**: <https://osu.ppy.sh/b/{beatmap_id}>."
    ).format(
        limit=score_request_limit,
        sign=("!" if acc == 1 else "+") if score["perfect"] == "1" else "-",
        mods=Mods.format_mods(int(score["enabled_mods"])),
        acc=acc,
        artist=beatmap["artist"],
        title=beatmap["title"],
        version=beatmap["version"],
        stars=float(beatmap["difficultyrating"]),
        max_combo="/{}".format(beatmap["max_combo"]) if mode in (api.GameMode.Standard, api.GameMode.CTB) else "",
        scoreboard_rank="#{} ".format(rank) if rank else "",
        **score
    )


def updates_per_log():
    """ Returns the amount of updates needed before logging interval is met. """
    return logging_interval // (update_interval / 60)


def get_mode(member_id: str):
    """ Return the api.GameMode for the member with this id. """
    if member_id not in osu_config.data["mode"]:
        return api.GameMode.Standard

    value = int(osu_config.data["mode"][member_id])
    return api.GameMode(value)


@asyncio.coroutine
def update_user_data(client: discord.Client):
    """ Go through all registered members playing osu!, and update their data. """
    global osu_tracking

    # Go through each member playing and give them an "old" and a "new" subsection
    # for their previous and latest user data
    for member_id, profile in osu_config.data["profiles"].items():
        def check_playing(m):
            """ Check if a member has "osu!" in their Game name. """
            # The member doesn't even match
            if not m.id == member_id:
                return False

            # See if the member is playing
            if m.game and "osu!" in m.game.name:
                return True

            return False

        member = discord.utils.find(check_playing, client.get_all_members())

        # If the member is not playing anymore, remove them from the tracking data
        if not member:
            if member_id in osu_tracking:
                del osu_tracking[member_id]

            continue

        mode = get_mode(member_id).value

        # User is already tracked
        if member_id in osu_tracking:
            # Move the "new" data into the "old" data of this user
            osu_tracking[member_id]["old"] = osu_tracking[member_id]["new"]
        else:
            # If this is the first time, update the user's list of scores for later
            scores = yield from api.get_user_best(u=profile, type="id", limit=score_request_limit, m=mode)
            osu_tracking[member_id] = dict(member=member, scores=scores)

        # Update the "new" data
        user_data = yield from api.get_user(u=profile, type="id", m=mode)
        osu_tracking[member_id]["new"] = user_data


@asyncio.coroutine
def get_new_score(member_id: str):
    """ Compare old user scores with new user scores and return the discovered
    new score if there is any. When a score is returned, it's position in the
    player's top plays can be retrieved with score["pos"]. """

    # Download a list of the user's scores
    profile = osu_config.data["profiles"][member_id]
    scores = yield from api.get_user_best(u=profile, type="id", limit=score_request_limit, m=get_mode(member_id).value)

    # Compare the scores from top to bottom and try to find a new one
    for i, score in enumerate(scores):
        if score not in osu_tracking[member_id]["scores"]:
            osu_tracking[member_id]["scores"] = scores
            score["pos"] = i
            return score
    else:
        return None


def get_diff(old, new, value):
    """ Get the difference between old and new osu! user data. """
    return float(new[value]) - float(old[value])


def get_notify_channel(server: discord.Server):
    """ Find the notifying channel or return the server. """
    channel = discord.utils.find(lambda c: "osu" in c.name, server.channels)
    return channel or server


@asyncio.coroutine
def notify_pp(client: discord.Client):
    """ Notify any differences in pp and post the scores + rank/pp gained. """
    for member_id, data in osu_tracking.items():
        # Only update pp when there is actually a difference
        if "old" not in data:
            continue

        old, new = data["old"], data["new"]

        # At this point, there is a difference in pp and we want to notify this
        pp_diff = get_diff(old, new, "pp_raw")

        # There is no difference in pp, therefore we move on to the next member
        if pp_diff == 0:
            continue

        # If the difference is too small, move on
        if pp_threshold > pp_diff > pp_threshold * -1:
            continue

        rank_diff = get_diff(old, new, "pp_rank") * -1
        country_rank_diff = get_diff(old, new, "pp_country_rank") * -1
        accuracy_diff = get_diff(old, new, "accuracy")  # Percent points difference

        # Since the user got pp they probably have a new score in their own top 100
        # If there is a score, there is also a beatmap
        score = yield from get_new_score(member_id)
        member = data["member"]
        mode = get_mode(member_id)

        # If a new score was found, format the score
        if score:
            beatmap_search = yield from api.get_beatmaps(b=int(score["beatmap_id"]))
            beatmap = api.lookup_beatmap(beatmap_search)
            scoreboard_rank = api.rank_from_events(new["events"], score["beatmap_id"])
            m = "{} (`{}`) ".format(member.mention, new["username"]) + \
                format_new_score(mode, score, beatmap, scoreboard_rank) + "\n"

        # There was not enough pp to get a top score, so add the name without mention
        else:
            m = "**{}** " + "(`{}`) ".format(new["username"])

        # Always add the difference in pp along with the ranks
        m += format_user_diff(mode, pp_diff, rank_diff, country_rank_diff, accuracy_diff, old["country"], new)

        # Send the message to all servers
        for server in client.servers:
            if member in server.members:
                channel = get_notify_channel(server)

                # Add the display name in this server when we don't mention
                if not score:
                    m = m.format(member.display_name)

                yield from client.send_message(channel, m)


@asyncio.coroutine
def on_ready(client: discord.Client):
    """ Handle every event. """
    # Notify the owner when they have not set their API key
    if osu_config.data["key"] == "change to your api key":
        logging.warning("osu! functionality is unavailable until an API key is provided")

    while not client.is_closed:
        try:
            yield from asyncio.sleep(update_interval)

            # First, update every user's data
            yield from update_user_data(client)

            # Next, check for any differences in pp between the "old" and the "new" subsections
            # and notify any servers
            yield from notify_pp(client)
        # We don't want to stop updating scores even if something breaks
        except:
            print_exc()
        finally:
            pass
            # TODO: setup logging
            # # Send info on how many requests were sent the last 30 minutes (60 loops)
            # updated += 1
            #
            # if updated % updates_per_log() == 0:
            #     logging.info("Requested osu! scores {} times in {} minutes.".format(sent_requests, logging_interval))
            #     sent_requests = 0


@plugins.command()
def osu(client: discord.Client, message: discord.Message, member: Annotate.Member=Annotate.Self):
    """ Handle osu! commands.

    When your user is linked, this plugin will check if you are playing osu!
    (your profile would have `playing osu!`), and send updates whenever you set a
    new top score. """
    # Make sure the member is assigned
    assert member.id in osu_config.data["profiles"], "No osu! profile assigned to **{}**!".format(member.name)

    user_id = osu_config.data["profiles"][member.id]

    # Set the signature color to that of the role color
    color = "pink" if member.color == discord.Color.default() \
        else "#{0:02x}{1:02x}{2:02x}".format(*member.color.to_tuple())

    # Download and upload the signature
    signature = yield from utils.download_file("http://lemmmy.pw/osusig/sig.php",
                                               colour=color, uname=user_id, pp=True,
                                               countryrank=True, xpbar=True, mode=get_mode(member.id).value)
    yield from client.send_file(message.channel, signature, filename="sig.png")

    yield from client.say(message, "<https://osu.ppy.sh/u/{}>".format(user_id))


@osu.command()
def link(client: discord.Client, message: discord.Message, name: Annotate.LowerContent):
    """ Tell the bot who you are on osu!. """
    osu_user = yield from api.get_user(u=name)

    # Check if the osu! user exists
    assert osu_user, "osu! user `{}` does not exist.".format(name)

    # Clear the scores when changing user
    if message.author.id in osu_tracking:
        del osu_tracking[message.author.id]

    # Assign the user using their unique user_id
    osu_config.data["profiles"][message.author.id] = osu_user["user_id"]
    osu_config.data["mode"][message.author.id] = api.GameMode.Standard.value
    osu_config.save()
    yield from client.say(message, "Set your osu! profile to `{}`.".format(osu_user["username"]))


@osu.command()
def unlink(client: discord.Client, message: discord.Message, member: Annotate.Member=Annotate.Self):
    """ Unlink your osu! account or unlink the member specified (**Owner only**). """
    # The message author is allowed to unlink himself
    # If a member is specified and the member is not the owner, set member to the author
    if not utils.is_owner(message.author):
        member = message.author

    # The member might not be linked to any profile
    assert member.id in osu_config.data["profiles"], "No osu! profile assigned to **{}**!".format(member.name)

    # Unlink the given member (usually the message author)
    del osu_config.data["profiles"][member.id]
    osu_config.save()
    yield from client.say(message, "Unlinked **{}'s** osu! profile.".format(member.name))


@osu.command(error="The specified gamemode does not exist.")
def gamemode(client: discord.Client, message: discord.Message, mode: api.GameMode.get_mode):
    """ Set the gamemode for the specified member.

    Gamemodes are `Standard`, `Taiko`, `CTB` and `Mania`. """
    assert message.author.id in osu_config.data["profiles"], \
        "No osu! profile assigned to **{}**!".format(message.author.name)

    osu_config.data["mode"][message.author.id] = mode.value
    osu_config.save()

    # Clear the scores when changing mode
    if message.author.id in osu_tracking:
        del osu_tracking[message.author.id]

    yield from client.say(message, "Set your gamemode to **{}**.".format(mode.name))


@osu.command()
def url(client: discord.Client, message: discord.Message, member: Annotate.Member=Annotate.Self):
    """ Display the member's osu! profile URL. """
    # Member might not be registered
    assert member.id in osu_config.data["profiles"], "No osu! profile assigned to **{}**!".format(member.name)

    # Send the URL since the member is registered
    yield from client.say(message, "**{0.display_name}'s profile:** <https://osu.ppy.sh/u/{1}>".format(
        member, osu_config.data["profiles"][member.id]))


@osu.command(name="pp")
def pp_(client: discord.Client, message: discord.Message, beatmap_url: str.lower, *options):
    """ Calculate and return the would be pp using `oppai`.

    Options are a parsed set of command-line arguments:  /
    `([acc]% | [num_100s]x100 [num_50s]x50) +[mods] [combo]x [misses]m scorev[scoring_version]`"""
    global last_calc_beatmap

    # This service is only supported on Linux as of yet
    assert platform.system() == "Linux", "This service is unsupported since the bot is not hosted using Linux."

    # Make sure the bot has access to "oppai" lib
    assert os.path.exists(os.path.join(oppai_path, "oppai")), \
        "This service is unavailable until the owner sets up the `oppai` lib."

    # Only download and request when the id is different from the last check
    if last_calc_beatmap["beatmap_id"] not in beatmap_url and last_calc_beatmap["beatmapset_id"] not in beatmap_url:
        # Parse beatmap URL and download the beatmap .osu
        try:
            beatmap = yield from api.beatmap_from_url(beatmap_url)
        except Exception as e:
            yield from client.say(message, e)
            return

        # Download and save the beatmap pp_map.osu
        beatmap_file = yield from utils.download_file(host + "osu/" + str(beatmap["beatmap_id"]))
        with open(os.path.join(oppai_path, "pp_map.osu"), "wb") as f:
            f.write(beatmap_file)
    else:
        beatmap = last_calc_beatmap

    last_calc_beatmap = beatmap

    command_args = [os.path.join(oppai_path, "oppai"), os.path.join(oppai_path, "pp_map.osu")]

    # Add additional options
    if options:
        command_args.extend(options)

    command_stream = Popen(command_args, universal_newlines=True, stdout=PIPE)
    output = command_stream.stdout.read()
    match = re.search(r"(?P<pp>[0-9.e+]+)pp", output)

    # Something went wrong with our service
    assert match, "A problem occurred when parsing the beatmap."

    # We're done! Tell the user how much this score is worth.
    yield from client.say(message, "*{artist} - {title}* **[{version}] {1}** would be worth `{0:,}pp`.".format(
        float(match.group("pp")), " ".join(options), **beatmap))


@osu.command()
@utils.owner
def debug(client: discord.Client, message: discord.Message):
    """ Display some debug info. """
    yield from client.say(message, "Sent `{}` requests since the bot started (`{}`).\n"
                                   "Members registered for update: {}".format(
        api.requests_sent,
        client.time_started.ctime(),
        utils.format_members(*[d["member"] for d in osu_tracking.values()])
    ))
