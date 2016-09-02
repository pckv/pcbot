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
import os
import platform
import re
from datetime import datetime
from traceback import print_exc

import asyncio
import discord

import plugins
from pcbot import Config, utils, Annotate
from plugins.osulib import api, Mods

osu_config = Config("osu", data=dict(key="change to your api key", profiles={}, mode={}, server={}))
osu_tracking = {}  # Saves the requested data or deletes whenever the user stops playing (for comparisons)
update_interval = 30  # The pause time in seconds between updates
time_elapsed = 0  # The registered time it takes to process all information between updates (changes each update)
logging_interval = 30  # The time it takes before posting logging information to the console. TODO: setup logging
rank_regex = re.compile(r"#\d+")

pp_threshold = 0.15
score_request_limit = 100
member_timeout = 2  # How long to wait before removing a member from the register (update_interval * value seconds)
max_diff_length = 32

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


def format_new_score(mode: api.GameMode, score: dict, beatmap: dict, rank: int, stream_url: str=None):
    """ Format any osu!Standard score. There should be a member name/mention in front of this string. """
    acc = calculate_acc(mode, score)
    return (
        "set a new best (`#{pos}/{limit}`) on *{artist} - {title}* **[{version}] {stars:.2f}\u2605**\n"
        "**{pp}pp, {rank} {scoreboard_rank}+{mods}**"
        "```diff\n"
        "  acc     300s    100s    50s     miss    combo\n"
        "{sign} {acc:<8.2%}{count300:<8}{count100:<8}{count50:<8}{countmiss:<8}{maxcombo}{max_combo}```"
        "**Profile**: <https://osu.ppy.sh/u/{user_id}>\n"
        "**Beatmap**: <https://osu.ppy.sh/b/{beatmap_id}>"
        "{live}"
    ).format(
        limit=score_request_limit,
        sign="!" if acc == 1 else ("+" if score["perfect"] == "1" else "-"),
        mods=Mods.format_mods(int(score["enabled_mods"])),
        acc=acc,
        artist=beatmap["artist"].replace("*", "\*").replace("_", "\_"),
        title=beatmap["title"].replace("*", "\*").replace("_", "\_"),
        version=beatmap["version"],
        stars=float(beatmap["difficultyrating"]),
        max_combo="/{}".format(beatmap["max_combo"]) if mode in (api.GameMode.Standard, api.GameMode.CTB) else "",
        scoreboard_rank="#{} ".format(rank) if rank else "",
        live="\n**Watch live @** <{}>".format(stream_url) if stream_url else "",
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
            if m.game and ("osu" in m.game.name.lower() or rank_regex.search(m.game.name)):
                return True

            return False

        member = discord.utils.find(check_playing, client.get_all_members())

        # If the member is not playing anymore, remove them from the tracking data
        if not member:
            if member_id in osu_tracking:
                del osu_tracking[member_id]

            continue

        mode = get_mode(member_id).value
        user_data = yield from api.get_user(u=profile, type="id", m=mode)

        # Just in case something goes wrong, we skip this member (these things are usually one-time occurances)
        if user_data is None:
            continue

        # User is already tracked
        if member_id in osu_tracking:
            # Move the "new" data into the "old" data of this user
            osu_tracking[member_id]["old"] = osu_tracking[member_id]["new"]
        else:
            # If this is the first time, update the user's list of scores for later
            scores = yield from api.get_user_best(u=profile, type="id", limit=score_request_limit, m=mode)
            osu_tracking[member_id] = dict(member=member, scores=scores)

        # Update the "new" data
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
            return dict(score, pos=i + 1)
    else:
        return None


def get_diff(old, new, value):
    """ Get the difference between old and new osu! user data. """
    return float(new[value]) - float(old[value])


def get_notify_channels(server: discord.Server, data_type: str):
    """ Find the notifying channel or return the server. """
    if server.id not in osu_config.data["server"]:
        return None

    if data_type + "-channels" not in osu_config.data["server"][server.id]:
        return None

    return [server.get_channel(s) for s in osu_config.data["server"][server.id][data_type + "-channels"]
            if server.get_channel(s)]


@asyncio.coroutine
def notify_pp(client: discord.Client, member_id: str, data: dict):
    """ Notify any differences in pp and post the scores + rank/pp gained. """
    # Only update pp when there is actually a difference
    if "old" not in data:
        return

    old, new = data["old"], data["new"]

    # At this point, there is a difference in pp and we want to notify this
    pp_diff = get_diff(old, new, "pp_raw")

    # There is no difference in pp, therefore we move on to the next member
    if pp_diff == 0:
        return

    # If the difference is too small, move on
    if pp_threshold > pp_diff > pp_threshold * -1:
        return

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
        beatmap_search = yield from api.get_beatmaps(b=int(score["beatmap_id"]), m=mode.value, a=1)
        beatmap = api.lookup_beatmap(beatmap_search)
        scoreboard_rank = api.rank_from_events(new["events"], score["beatmap_id"])
        stream_url = member.game.url if member.game is not None else None
        m = "{} " + "(`{}`) ".format(new["username"]) + \
            format_new_score(mode, score, beatmap, scoreboard_rank, stream_url) + "\n"

    # There was not enough pp to get a top score, so add the name without mention
    else:
        m = "{} " + "(`{}`) ".format(new["username"])

    # Always add the difference in pp along with the ranks
    m += format_user_diff(mode, pp_diff, rank_diff, country_rank_diff, accuracy_diff, old["country"], new)

    # Send the message to all servers
    for server in client.servers:
        member = server.get_member(member_id)
        channels = get_notify_channels(server, "score")

        if not member or not channels:
            continue

        for i, channel in enumerate(channels):
            try:
                yield from client.send_message(channel, m.format(member.mention) if i == 0 and score else
                                                        m.format("**" + member.display_name + "**"))
            except discord.errors.Forbidden:
                pass


def format_beatmapset_diffs(beatmapset: dict):
    """ Format some difficulty info on a beatmapset. """
    # Get the longest difficulty name
    diff_length = len(max((diff["version"] for diff in beatmapset), key=len))
    if diff_length > max_diff_length:
        diff_length = max_diff_length
    elif diff_length < len("version"):
        diff_length = len("version")

    m = "```xl\n" \
        "mode  {version: <{diff_len}}  |  stars   cs   ar   od   hp   drain".format(
        version="version", diff_len=diff_length)

    for diff in sorted(beatmapset, key=lambda d: float(d["difficultyrating"])):
        diff_name = diff["version"].replace("'", "`")
        m += "\n{gamemode: <6}{name: <{diff_len}}  |  " \
             "{stars: <8}{diff_size: <5}{diff_approach: <5}{diff_overall: <5}{diff_drain: <5}{drain}".format(
            gamemode=api.GameMode(int(diff["mode"])).name[0],
            name=diff_name if len(diff_name) < max_diff_length else diff_name[:29] + "...",
            diff_len=diff_length,
            stars="{:.2f}\u2605".format(float(diff["difficultyrating"])),
            drain="{}:{:02}".format(*divmod(int(diff["hit_length"]), 60)),
            **diff
        )

    return m + "```"


def format_map_status(member_name: str, status_format: str, beatmapset: dict):
    """ Format the status update of a beatmap"""
    return status_format.format(name=member_name, **beatmapset[0]) + \
           format_beatmapset_diffs(beatmapset) + \
           "**Beatmap**: <{}s/{}>".format(host, beatmapset[0]["beatmapset_id"])


@asyncio.coroutine
def notify_maps(client: discord.Client, member_id: str, data: dict):
    """ Notify any map updates, such as update, resurrect and qualified. """
    # Only update when there is a difference
    if "old" not in data:
        return

    # Get the old and the new events
    old, new = data["old"]["events"], data["new"]["events"]

    # If nothing has changed, move on to the next member
    if old == new:
        return

    # Get the new events
    events = []
    for event in new:
        if event in old:
            break

        # Since the events are displayed on the profile from newest to oldest,
        # we want to post the oldest first
        events.insert(0, event)

    # Format and post the events
    for event in events:
        html = event["display_html"]

        # Get and format the type of event
        if "submitted" in html:
            status_format = "\U0001F310 **{name}** has submitted a new beatmap **{artist} - {title}**"
        elif "updated" in html:
            status_format = "\U0001F53C **{name}** has updated the beatmap **{artist} - {title}**"
        elif "revived" in html:
            status_format = "\U0001F64F **{artist} - {title}** has been revived from eternal slumber by **{name}**"
        elif "qualified" in html:
            status_format = "\U0001F497 **{artist} - {title}** by **{name}** has just been qualified!"
        else:  # We discard any other events
            continue

        # We'll sleep a little bit to let the beatmap API catch up with the change
        yield from asyncio.sleep(10)

        # Try returning the beatmap info 3 times with a span of 20 seconds.
        # This might be needed when new maps are submitted.
        for _ in range(3):
            beatmapset = yield from api.get_beatmaps(s=event["beatmapset_id"])
            if beatmapset:
                break
            yield from asyncio.sleep(20)
        else:
            # Oh well, false positive?
            continue

        # Send the message to all servers
        for server in client.servers:
            member = server.get_member(member_id)
            channels = get_notify_channels(server, "map")

            if not member or not channels:
                continue

            for channel in channels:
                try:
                    yield from client.send_message(channel,
                                                   format_map_status(member.display_name, status_format, beatmapset))
                except discord.errors.Forbidden:
                    pass


@asyncio.coroutine
def on_ready(client: discord.Client):
    """ Handle every event. """
    global time_elapsed

    # Notify the owner when they have not set their API key
    if osu_config.data["key"] == "change to your api key":
        logging.warning("osu! functionality is unavailable until an API key is provided")

    while not client.is_closed:
        try:
            yield from asyncio.sleep(update_interval)
            started = datetime.now()

            # First, update every user's data
            yield from update_user_data(client)

            # Next, check for any differences in pp between the "old" and the "new" subsections
            # and notify any servers
            for member_id, data in osu_tracking.items():
                asyncio.async(notify_pp(client, member_id, data))

            # Check for any differences in the users' events and post about map updates
            for member_id, data in osu_tracking.items():
                asyncio.async(notify_maps(client, member_id, data))
        # We don't want to stop updating scores even if something breaks
        except:
            print_exc()
        finally:
            pass
            # TODO: setup logging

            # Save the time elapsed since we started the update
            time_elapsed = (datetime.now() - started).total_seconds()


@plugins.command(aliases="circlesimulator eba")
def osu(client: discord.Client, message: discord.Message, member: Annotate.Member=Annotate.Self,
        mode: api.GameMode.get_mode=None):
    """ Handle osu! commands.

    When your user is linked, this plugin will check if you are playing osu!
    (your profile would have `playing osu!`), and send updates whenever you set a
    new top score. """
    # Make sure the member is assigned
    assert member.id in osu_config.data["profiles"], "No osu! profile assigned to **{}**!".format(member.name)

    user_id = osu_config.data["profiles"][member.id]
    mode = get_mode(member.id) if mode is None else mode

    # Set the signature color to that of the role color
    color = "pink" if member.color == discord.Color.default() \
        else "#{0:02x}{1:02x}{2:02x}".format(*member.color.to_tuple())

    # Download and upload the signature
    signature, _ = yield from utils.download_file("http://lemmmy.pw/osusig/sig.php",
                                                  colour=color, uname=user_id, pp=True,
                                                  countryrank=True, xpbar=True, mode=mode.value)
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


@osu.command(aliases="mode m", error="The specified gamemode does not exist.")
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
def url(client: discord.Client, message: discord.Message, member: Annotate.Member=Annotate.Self,
        section: str.lower=None):
    """ Display the member's osu! profile URL. """
    # Member might not be registered
    assert member.id in osu_config.data["profiles"], "No osu! profile assigned to **{}**!".format(member.name)

    # Send the URL since the member is registered
    yield from client.say(message, "**{0.display_name}'s profile:** <https://osu.ppy.sh/u/{1}{2}>".format(
        member, osu_config.data["profiles"][member.id], "#_{}".format(section) if section else ""))


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
        beatmap_file, _ = yield from utils.download_file(host + "osu/" + str(beatmap["beatmap_id"]))
        with open(os.path.join(oppai_path, "pp_map.osu"), "wb") as f:
            f.write(beatmap_file)
    else:
        beatmap = last_calc_beatmap

    last_calc_beatmap = beatmap

    command_args = [os.path.join(oppai_path, "oppai"), os.path.join(oppai_path, "pp_map.osu")]

    # Add additional options
    if options:
        command_args.extend(options)

    process = yield from asyncio.create_subprocess_exec(*command_args, stdout=asyncio.subprocess.PIPE)
    output, _ = yield from process.communicate()
    match = re.search(r"(?P<pp>[0-9.e+]+)pp", output.decode("utf-8"))

    # Something went wrong with our service
    assert match, "A problem occurred when parsing the beatmap."

    # We're done! Tell the user how much this score is worth.
    yield from client.say(message, "*{artist} - {title}* **[{version}] {1}** would be worth `{0:,}pp`.".format(
        float(match.group("pp")), " ".join(options), **beatmap))


def init_server_config(server: discord.Server):
    """ Initializes the config when it's not already set. """
    if server.id not in osu_config.data["server"]:
        osu_config.data["server"][server.id] = {}
        osu_config.save()


@osu.command(aliases="configure cfg")
def config(client, message, _: utils.placeholder):
    """ Manage configuration for this plugin. """
    pass


@config.command(alias="score")
@utils.permission("manage_server")
def scores(client: discord.Client, message: discord.Message, *channels: Annotate.Channel):
    """ Set which channels to post scores to. """
    init_server_config(message.server)
    osu_config.data["server"][message.server.id]["score-channels"] = list(c.id for c in channels)
    osu_config.save()
    yield from client.say(message, "**Notifying scores in {}.**".format(
        utils.format_objects(*channels) or "no channels"))


@config.command(alias="map")
@utils.permission("manage_server")
def maps(client: discord.Client, message: discord.Message, *channels: Annotate.Channel):
    """ Set which channels to post map updates to. """
    init_server_config(message.server)
    osu_config.data["server"][message.server.id]["map-channels"] = list(c.id for c in channels)
    osu_config.save()
    yield from client.say(message, "**Notifying map updates in {}.**".format(
        utils.format_objects(*channels) or "no channels"))


@osu.command()
@utils.owner
def debug(client: discord.Client, message: discord.Message):
    """ Display some debug info. """
    yield from client.say(message, "Sent `{}` requests since the bot started (`{}`).\n"
                                   "Spent `{:.3f}` seconds last update.\n"
                                   "Members registered for update: {}".format(
        api.requests_sent, client.time_started.ctime(),
        time_elapsed,
        utils.format_objects(*[d["member"] for d in osu_tracking.values()], dec="`")
    ))
