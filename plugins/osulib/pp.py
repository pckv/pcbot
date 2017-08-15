""" Implement pp calculation features using pyoppai.
    https://github.com/Francesco149/oppai/tree/master/pyoppai
"""

import os
from collections import namedtuple

from pcbot import utils
from . import api
from .args import parse as parse_options

try:
    import pyoppai
except:
    pyoppai = None


host = "https://osu.ppy.sh/"

Beatmap = namedtuple("Beatmap", "url size")
PPStats = namedtuple("PPStats", "pp stars artist title version")
ClosestPPStats = namedtuple("ClosestPPStats", "acc pp stars artist title version")
last_calc_beatmap = Beatmap(url=None, size=None)

oppai_path = "plugins/osulib/oppai/"
beatmap_path = os.path.join(oppai_path, "pp_map.osu")


async def is_osu_file(url: str):
    """ Returns True if the url links to a .osu file. """
    headers = await utils.retrieve_headers(url)
    return "text/plain" in headers.get("Content-Type", "") and ".osu" in headers.get("Content-Disposition", "")


async def download_beatmap(beatmap_url: str):
    """ Download the .osu file of the beatmap with the given url.

    This returns the Beatmap tuple.
    """
    global last_calc_beatmap

    # Return cached information
    if beatmap_url == last_calc_beatmap.url:
        return last_calc_beatmap

    # Parse the url and find the link to the .osu file
    try:
        beatmap_id = await api.beatmap_from_url(beatmap_url, return_type="id")
    except SyntaxError as e:
        # Since the beatmap isn't an osu.ppy.sh url, we'll see if it's a .osu file
        if not await is_osu_file(beatmap_url):
            raise ValueError(e)

        file_url = beatmap_url
    else:
        file_url = host + "osu/" + str(beatmap_id)

    # Download the beatmap using the url
    beatmap_file = await utils.download_file(file_url)
    with open(beatmap_path, "wb") as f:
        f.write(beatmap_file)

    last_calc_beatmap = Beatmap(url=beatmap_url, size=len(beatmap_file))
    return last_calc_beatmap


def create_ctx(beatmap: Beatmap):
    """ Generates and returns pyoppai ctx and beatmap ctx. """
    ctx = pyoppai.new_ctx()
    beatmap_ctx = pyoppai.new_beatmap(ctx)

    # Setup the buffer to be 1kB larger than the .osu
    buffer_size = beatmap.size + 1024
    buffer = pyoppai.new_buffer(buffer_size)

    # Parse beatmap
    pyoppai.parse(beatmap_path, beatmap_ctx, buffer, buffer_size, False, os.path.dirname(oppai_path))

    return ctx, beatmap_ctx


def apply_settings(beatmap_ctx, args):
    """ Applies settings to the ctx using parsed arguments.

    Also return the mods bitmask for use during pp calculation.
    """
    # Find the mod bitmask and optionally apply mods
    mods_bitmask = sum(mod.value for mod in args.mods) if args.mods else 0
    if not mods_bitmask == 0:
        pyoppai.apply_mods(beatmap_ctx, mods_bitmask)

    # Set any optional beatmap settings
    if args.cs is not None:
        pyoppai.set_cs(beatmap_ctx, args.cs)
    if args.ar is not None:
        pyoppai.set_ar(beatmap_ctx, args.ar)
    if args.od is not None:
        pyoppai.set_od(beatmap_ctx, args.od)

    return mods_bitmask


async def calculate_pp(beatmap_url: str, *options):
    """ Return a PPStats namedtuple from this beatmap, or a ClosestPPStats namedtuple
    when [pp_value]pp is given in the options. """
    if pyoppai is None:
        return None

    beatmap = await download_beatmap(beatmap_url)
    args = parse_options(*options)

    # If the pp arg is given, return using the closest pp function
    if args.pp is not None:
        return await find_closest_pp(beatmap, args)

    ctx, beatmap_ctx = create_ctx(beatmap)

    # Create the difficulty context for calculating
    diff_ctx = pyoppai.new_d_calc_ctx(ctx)
    mods_bitmask = apply_settings(beatmap_ctx, args)
    stars, aim, speed, _, _, _, _ = pyoppai.d_calc(diff_ctx, beatmap_ctx)

    # Calculate using only acc when acc is specified
    if args.acc < 100:
        acc, pp, _, _, _ = pyoppai.pp_calc_acc(
            ctx, aim, speed, beatmap_ctx, args.acc, mods_bitmask, args.combo, args.misses, args.score_version)
    else:
        acc, pp, _, _, _ = pyoppai.pp_calc(
            ctx, aim, speed, beatmap_ctx, mods_bitmask, args.combo, args.misses, args.c300, args.c100, args.c50, args.score_version)

    return PPStats(pp, stars, pyoppai.artist(beatmap_ctx), pyoppai.title(beatmap_ctx), pyoppai.version(beatmap_ctx))


async def find_closest_pp(beatmap, args):
    """ Find the accuracy required to get the given amount of pp from this map. """
    if pyoppai is None:
        return None

    ctx, beatmap_ctx = create_ctx(beatmap)

    # Create the difficulty context for calculating
    diff_ctx = pyoppai.new_d_calc_ctx(ctx)
    mods_bitmask = apply_settings(beatmap_ctx, args)
    stars, aim, speed, _, _, _, _ = pyoppai.d_calc(diff_ctx, beatmap_ctx)

    # Define a partial command for easily setting the pp value by 100s count
    def calc(accuracy: float):
        return pyoppai.pp_calc_acc(
            ctx, aim, speed, beatmap_ctx, accuracy, mods_bitmask, args.combo, args.misses, args.score_version)[1]

    # Find the smallest possible value oppai is willing to give
    min_pp = calc(accuracy=0.0)
    if args.pp <= min_pp:
        raise ValueError("The given pp value is too low (oppai gives **{:.02f}pp** at **0% acc**).".format(min_pp))

    # Calculate the max pp value by using 100% acc
    previous_pp = calc(accuracy=100.0)

    if args.pp >= previous_pp:
        raise ValueError("PP value should be below **{:.02f}pp** for this map.".format(previous_pp))

    dec = .05
    acc = 100.0 - dec
    while True:
        current_pp = calc(accuracy=acc)
        print(acc, dec, current_pp)

        # Stop when we find a pp value between the current 100 count and the previous one
        if current_pp <= args.pp <= previous_pp:
            break
        else:
            previous_pp = current_pp
            acc -= dec

    # Find the closest pp of our two values, and return the amount of 100s
    closest_pp = min([previous_pp, current_pp], key=lambda v: abs(args.pp - v))
    acc = acc if closest_pp == current_pp else acc + dec
    return ClosestPPStats(round(acc, 2), closest_pp, stars, pyoppai.artist(beatmap_ctx), pyoppai.title(beatmap_ctx),
                          pyoppai.version(beatmap_ctx))
