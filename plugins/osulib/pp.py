""" Implement pp calculation features using oppai.
https://github.com/Francesco149/oppai
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
PPStats = namedtuple("PPStats", "pp acc stars artist title version")
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
        # Since the beatmap isn't a osu.ppy.sh url, we'll see if it's a .osu file
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


async def calculate_pp(beatmap_url: str, *options):
    """ Return a PPStats namedtuple from this beatmap. """
    if pyoppai is None:
        return None

    beatmap = await download_beatmap(beatmap_url)
    ctx, beatmap_ctx = create_ctx(beatmap)
    args = parse_options(*options)

    # Create the difficulty context for calculating
    diff_ctx = pyoppai.new_d_calc_ctx(ctx)

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

    stars, aim, speed, _, _, _, _ = pyoppai.d_calc(diff_ctx, beatmap_ctx)

    # Calculate using only acc when acc is specified
    if args.acc < 100:
        acc, pp, _, _, _ = pyoppai.pp_calc_acc(
            ctx, aim, speed, beatmap_ctx, args.acc, mods_bitmask, args.combo, args.misses, args.score_version)
    else:
        acc, pp, _, _, _ = pyoppai.pp_calc(
            ctx, aim, speed, beatmap_ctx, mods_bitmask, args.combo, args.misses, args.c300, args.c100, args.c50, args.score_version)

    return PPStats(pp, acc, stars, pyoppai.artist(beatmap_ctx), pyoppai.title(beatmap_ctx), pyoppai.version(beatmap_ctx))


async def _find_closest_pp(beatmap_url: str, pp: float, *options):
    """ Run oppai on a beatmap with increasing amount of 100s until it gives
    pp as close as possible to the given pp value.

    It is a given that amount of 100s should not be included in options.

    This function returns the amount of 100s needed, not the pp. """
    # TODO: reimplement
    previous_pp = max_pp = await calculate_pp(beatmap_url, *options)
    min_pp = round(7/8 * max_pp, 2)

    # The pp value must be within a close range of what the map actually gives
    if pp < min_pp or pp > max_pp:
        raise ValueError("The given pp value must be between **{}pp** and **{}pp** for this map.".format(min_pp, max_pp))

    c100 = 1
    while True:
        new_options = list(options)
        new_options.append("{}x100".format(c100))
        current_pp = await calculate_pp(beatmap_url, *new_options)

        # Stop when we find a pp value between the current 100 count and the previous one
        if current_pp <= pp <= previous_pp:
            break
        else:
            previous_pp = current_pp
            c100 += 1

    # Find the closest pp of our two values, and return the amount of 100s
    closest_pp = min([previous_pp, current_pp], key=lambda v: abs(pp - v))
    return c100 if closest_pp == current_pp else c100 - 1