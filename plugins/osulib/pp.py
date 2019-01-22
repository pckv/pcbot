""" Implement pp calculation features using pyttanko.
    https://github.com/Francesco149/pyttanko
"""

import os
from collections import namedtuple
import logging

from pcbot import utils
from . import api
from .args import parse as parse_options

try:
    import pyttanko
except:
    pyttanko = None


host = "https://osu.ppy.sh/"

CachedBeatmap = namedtuple("CachedBeatmap", "url_or_id beatmap")
PPStats = namedtuple("PPStats", "pp stars artist title version")
ClosestPPStats = namedtuple("ClosestPPStats", "acc pp stars artist title version")

plugin_path = "plugins/osulib/"
beatmap_path = os.path.join(plugin_path, "map.osu")
cached_beatmap = CachedBeatmap(url_or_id=None, beatmap=None)


async def is_osu_file(url: str):
    """ Returns True if the url links to a .osu file. """
    headers = await utils.retrieve_headers(url)
    return "text/plain" in headers.get("Content-Type", "") and ".osu" in headers.get("Content-Disposition", "")


async def download_beatmap(beatmap_url_or_id):
    """ Download the .osu file of the beatmap with the given url, and save it to beatmap_path.

    :param beatmap_url_or_id: beatmap_url as str or the id as int
    """
    # Parse the url and find the link to the .osu file
    try:
        if type(beatmap_url_or_id) is str:
            beatmap_id = await api.beatmap_from_url(beatmap_url_or_id, return_type="id")
        else:
            beatmap_id = beatmap_url_or_id
    except SyntaxError as e:
        # Since the beatmap isn't an osu.ppy.sh url, we'll see if it's a .osu file
        if not await is_osu_file(beatmap_url_or_id):
            raise ValueError(e)

        file_url = beatmap_url_or_id
    else:
        file_url = host + "osu/" + str(beatmap_id)

    # Download the beatmap using the url
    beatmap_file = await utils.download_file(file_url)
    if not beatmap_file:
        raise ValueError("The given URL is invalid.")

    with open(beatmap_path, "wb") as f:
        f.write(beatmap_file)
    
    # one map apparently had a /ufeff at the very beginning of the file???
    # https://osu.ppy.sh/b/1820921
    if not beatmap_file.decode().strip("\ufeff \t").startswith("osu file format"):
        logging.error("Invalid file received from {}\nCheck {}".format(file_url, beatmap_path))
        raise ValueError("Could not download the .osu file.")


async def parse_map(beatmap_url_or_id):
    """ Download and parse the map with the given url or id, or return a newly parsed cached version.

    :param beatmap_url_or_id: beatmap_url as str or the id as int
    """
    global cached_beatmap

    parser = pyttanko.parser()

    # Parse from cache or load the .osu and parse new
    if beatmap_url_or_id == cached_beatmap.url_or_id:
        with open(beatmap_path, encoding="utf-8") as fp:
            beatmap = parser.map(fp, bmap=cached_beatmap.beatmap)
    else:
        await download_beatmap(beatmap_url_or_id)

        with open(beatmap_path, encoding="utf-8") as fp:
            beatmap = parser.map(fp)

        cached_beatmap = CachedBeatmap(url_or_id=beatmap_url_or_id, beatmap=beatmap)

    return beatmap


def apply_settings(beatmap, args):
    """ Applies difficulty settings to beatmap, and return the mods bitmask. """
    mods_bitmask = sum(mod.value for mod in args.mods) if args.mods else 0

    if args.ar:
        beatmap.ar = float(args.ar)
    if args.hp:
        beatmap.hp = float(args.hp)
    if args.od:
        beatmap.od = float(args.od)
    if args.cs:
        beatmap.cs = float(args.cs)

    return mods_bitmask


async def calculate_pp(beatmap_url_or_id, *options):
    """ Return a PPStats namedtuple from this beatmap, or a ClosestPPStats namedtuple
    when [pp_value]pp is given in the options.

    :param beatmap_url_or_id: beatmap_url as str or the id as int
    """
    if pyttanko is None:
        return None
    
    beatmap = await parse_map(beatmap_url_or_id)
    args = parse_options(*options)

    # When acc is provided, calculate the 300s, 100s and 50s
    c300, c100, c50 = args.c300, args.c100, args.c50
    if args.acc is not None:
        c300, c100, c50 = pyttanko.acc_round(args.acc, len(beatmap.hitobjects), args.misses)

    # Change the beatmap's difficulty settings if provided, and calculate the mod bitmask
    mods_bitmask = apply_settings(beatmap, args)

    # Calculate the star difficulty
    stars = pyttanko.diff_calc().calc(beatmap, mods_bitmask)

    # # If the pp arg is given, return using the closest pp function
    # if args.pp is not None:
    #     return await find_closest_pp(beatmap, args)

    # Calculate the pp
    pp, _, _, _, _ = pyttanko.ppv2(stars.aim, stars.speed, bmap=beatmap, mods=mods_bitmask, combo=args.combo,
                                   n300=c300, n100=c100, n50=c50, nmiss=args.misses,  score_version=args.score_version)
    
    return PPStats(pp, stars.total, beatmap.artist, beatmap.title, beatmap.version)


# async def find_closest_pp(beatmap, args):
#     """ Find the accuracy required to get the given amount of pp from this map. """
#     if pyttanko is None:
#         return None
#
#     ctx, beatmap_ctx = create_ctx(beatmap)
#
#     # Create the difficulty context for calculating
#     diff_ctx = pyoppai.new_d_calc_ctx(ctx)
#     mods_bitmask = apply_settings(beatmap_ctx, args)
#     stars, aim, speed, _, _, _, _ = pyoppai.d_calc(diff_ctx, beatmap_ctx)
#
#     # Define a partial command for easily setting the pp value by 100s count
#     def calc(accuracy: float):
#         return pyoppai.pp_calc_acc(
#             ctx, aim, speed, beatmap_ctx, accuracy, mods_bitmask, args.combo, args.misses, args.score_version)[1]
#
#     # Find the smallest possible value oppai is willing to give
#     min_pp = calc(accuracy=0.0)
#     if args.pp <= min_pp:
#         raise ValueError("The given pp value is too low (oppai gives **{:.02f}pp** at **0% acc**).".format(min_pp))
#
#     # Calculate the max pp value by using 100% acc
#     previous_pp = calc(accuracy=100.0)
#
#     if args.pp >= previous_pp:
#         raise ValueError("PP value should be below **{:.02f}pp** for this map.".format(previous_pp))
#
#     dec = .05
#     acc = 100.0 - dec
#     while True:
#         current_pp = calc(accuracy=acc)
#
#         # Stop when we find a pp value between the current 100 count and the previous one
#         if current_pp <= args.pp <= previous_pp:
#             break
#         else:
#             previous_pp = current_pp
#             acc -= dec
#
#     # Find the closest pp of our two values, and return the amount of 100s
#     closest_pp = min([previous_pp, current_pp], key=lambda v: abs(args.pp - v))
#     acc = acc if closest_pp == current_pp else acc + dec
#     return ClosestPPStats(round(acc, 2), closest_pp, stars, pyoppai.artist(beatmap_ctx), pyoppai.title(beatmap_ctx),
#                           pyoppai.version(beatmap_ctx))
