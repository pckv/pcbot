""" osu! commands

This plugin currently only assigns osu! profiles and notifies the server whenever they set a new top score (pp best).
The notifying is a near identical copy of plugins/twitch.py

Commands:
!osu
"""

import logging
from traceback import print_exc

import discord
import asyncio

from pcbot import Config, utils, Annotate
import plugins
from plugins.osulib import api, Mods

osu_config = Config("osu", data={"key": "change to your api key", "profiles": {}})
osu_tracking = {}  # Saves the requested data or deletes whenever the user stops playing (for comparisons)
update_interval = 30  # Seconds
logging_interval = 30  # Minutes

pp_threshold = 0.05
score_request_limit = 100

api.api_key = osu_config.data.get("key")


def calculate_acc(c50, c100, c300, miss):
    """ Calculate the accuracy using this formula: https://osu.ppy.sh/wiki/Accuracy#Standard """
    total_points_of_hits = int(c50) * 50 + int(c100) * 100 + int(c300) * 300
    total_number_of_hits = int(miss) + int(c50) + int(c100) + int(c300)

    return total_points_of_hits / (total_number_of_hits * 300)


def format_user_diff(pp: float, rank: int, country_rank: int, accuracy: float, iso: str, data: str):
    """ Get a bunch of differences and return a formatted string to send.
    iso is the country code. """
    formatted = ":information_source:`{}pp {:+.2f}pp`".format(data["pp_raw"], pp)
    formatted += (" :earth_africa:`#{}{}`".format(data["pp_rank"],
                                                   "" if int(rank) == 0 else " {:+,}".format(int(rank))))
    formatted += (" :flag_{}:`#{}{}`".format(iso.lower(), data["pp_country_rank"],
                                              "" if int(country_rank) == 0 else " {:+,}".format(int(country_rank))))
    if not round(accuracy, 3) == 0:
        formatted += (" {}`{:+.3f}%`".format(":chart_with_upwards_trend:"
                                             if accuracy > 0 else ":chart_with_downwards_trend:", accuracy))

    return formatted


def format_new_score(score: dict, beatmap: dict):
    """ Format any osu!Standard score. There should be a member name/mention in front of this string. """
    return (
        "set a new best on *{artist} - {title}* **[{version}] {stars:.2f}\u2605**\n"
        "**{pp}pp, {rank} +{mods}**"
        "```diff\n"
        "  acc     300s    100s    50s     miss    combo\n"
        "{sign} {acc:<8.2%}{count300:<8}{count100:<8}{count50:<8}{countmiss:<8}{maxcombo}/{max_combo}```"
        "**Profile**: <https://osu.ppy.sh/u/{user_id}>.\n"
        "**Beatmap**: <https://osu.ppy.sh/b/{beatmap_id}>."
    ).format(
        sign="+" if score["perfect"] == "1" else "-",
        mods=Mods.format_mods(int(score["enabled_mods"])),
        acc=calculate_acc(score["count50"], score["count100"], score["count300"], score["countmiss"]),
        artist=beatmap["artist"],
        title=beatmap["title"],
        version=beatmap["version"],
        stars=float(beatmap["difficultyrating"]),
        max_combo=beatmap["max_combo"],
        **score
    )


def updates_per_log():
    """ Returns the amount of updates needed before logging interval is met. """
    return logging_interval // (update_interval / 60)


@asyncio.coroutine
def update_user_data(client: discord.Client):
    """ Go through all registered members playing osu!, and update their data. """
    global osu_tracking

    # Go through each member playing and give them an "old" and a "new" subsection
    # for their previous and latest user data
    for member_id, profile in osu_config.data["profiles"].items():
        def check_playing(m):
            """ Check if a member has "osu!" in their Game name. """
            if m.id == member_id and m.game:
                if "osu!" in m.game.name:
                    return True

            return False

        member = discord.utils.find(check_playing, client.get_all_members())

        # If the member is not playing anymore, remove them from the tracking data
        if not member:
            if member_id in osu_tracking:
                del osu_tracking[member_id]

            continue

        # User is already tracked
        if member_id in osu_tracking:
            # Move the "new" data into the "old" data of this user
            osu_tracking[member_id]["old"] = osu_tracking[member_id]["new"]

        # If this is the first time, update the user's list of scores for later
        else:
            scores = yield from api.get_user_best(u=profile, type="id", limit=score_request_limit)

            osu_tracking[member_id] = dict(member=member)
            osu_tracking[member_id]["scores"] = scores

        # Update the "new" data
        user_data = yield from api.get_user(u=profile, type="id")
        osu_tracking[member_id]["new"] = user_data


@asyncio.coroutine
def get_new_score(member_id: str):
    """ Compare old user scores with new user scores and return
    the discovered new score if there is any. """

    # Download a list of the user's scores
    profile = osu_config.data["profiles"][member_id]
    scores = yield from api.get_user_best(u=profile, type="id", limit=score_request_limit)

    # Compare the scores from top to bottom and try to find a new one
    new_score = None

    for score in scores:
        if score not in osu_tracking[member_id]["scores"]:
            new_score = score

    osu_tracking[member_id]["scores"] = scores
    return new_score


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

        # If a new score was found, format the score
        if score:
            beatmap_search = yield from api.get_beatmaps(b=int(score["beatmap_id"]))
            beatmap = api.get_beatmap(beatmap_search)
            m = "{} (`{}`) ".format(member.mention, new["username"]) + format_new_score(score, beatmap) + "\n"

        # There was not enough pp to get a top score, so add the name without mention
        else:
            m = "**{}** " + "(`{}`) ".format(new["username"])

        # Always add the difference in pp along with the ranks
        m += format_user_diff(pp_diff, rank_diff, country_rank_diff, accuracy_diff, old["country"], new)

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


@plugins.command(usage="[username | link <user> | unlink [user]]")
def osu(client: discord.Client, message: discord.Message, member: Annotate.Member = None):
    """ Handle osu! commands.

    When your user is linked, this plugin will check if you are playing osu!
    (your profile would have `playing osu!`), and send updates whenever you set a
    new top score. """
    if not member:
        member = message.author

    # Member is not registered in osu! data.
    if member.id not in osu_config.data["profiles"]:
        yield from client.say(message, "No osu! profile assigned to **{}**!".format(member.name))
        return

    user_id = osu_config.data["profiles"][member.id]

    # Set the signature color to that of the role color
    color = "pink" if member.color == discord.Color.default() \
        else "#{0:02x}{1:02x}{2:02x}".format(*member.color.to_tuple())

    # Download and upload the signature
    signature = yield from utils.download_file("http://lemmmy.pw/osusig/sig.php",
                                               colour=color, uname=user_id, pp=True,
                                               countryrank=True, xpbar=True)
    yield from client.send_file(message.channel, signature, filename="sig.png")

    yield from client.say(message, "<https://osu.ppy.sh/u/{}>".format(user_id))


@osu.command()
def link(client: discord.Client, message: discord.Message, name: Annotate.LowerContent):
    """ Tell the bot who you are on osu!. """
    osu_user = yield from api.get_user(u=name)

    # Could not find a user by the specified name
    if not osu_user:
        yield from client.say(message, "osu! user `{}` does not exist.".format(name))
        return

    # Clear the scores when changing user
    if message.author.id in osu_tracking:
        del osu_tracking[message.author.id]

    # Assign the user using their unique user_id
    osu_config.data["profiles"][message.author.id] = osu_user["user_id"]
    osu_config.save()

    yield from client.say(message, "Set your osu! profile to `{}`.".format(osu_user["username"]))


@osu.command()
def unlink(client: discord.Client, message: discord.Message, member: Annotate.Member = None):
    """ Unlink your osu! account or the member specified. """
    # The message author wants to unlink someone and must be owner
    if member and not utils.is_owner(message.author):
        yield from client.say(message, "You must be owner to unlink other users.")
        return

    # The message author is allowed to unlink himself, and if a member is specified
    # the author would be the owner at this point
    if not member:
        member = message.author

    # The member is not linked
    if member.id not in osu_config.data["profiles"]:
        yield from client.say(message, "**{}** is not linked to an osu! profile.".format(member.name))

    # Unlink the given member (usually the message author)

    del osu_config.data["profiles"][member.id]
    osu_config.save()
    yield from client.say(message, "Unlinked **{}'s** osu! profile.".format(member.name))


@osu.command()
@utils.owner
def debug(client: discord.Client, message: discord.Message):
    """ Display some debug info. """
    yield from client.say(message, "Sent `{}` requests since the bot started (`{}`).".format(
        api.requests_sent,
        client.time_started.ctime()
    ))
