""" API integration for osu!

    Adds Mods enums with raw value calculations and some
    request functions. """

from enum import IntEnum

import asyncio

from pcbot import utils


api_url = "https://osu.ppy.sh/api/"
api_key = ""  # This variable can be changed to exclude the "k" parameter
requests_sent = 0


class Mods(IntEnum):
    """ Enum for displaying mods. """
    NF = 1
    EZ = 2
    NV = 4
    HD = 8
    HR = 16
    SD = 32
    DT = 64
    RX = 128
    HT = 256
    NC = 512
    FL = 1024
    Auto = 2048
    SO = 4096
    AP = 8192
    PF = 16384
    Key4 = 32768
    Key5 = 65536
    Key6 = 131072
    Key7 = 262144
    Key8 = 524288
    keyMod = Key4 | Key5 | Key6 | Key7 | Key8         # ¯\_(ツ)_/¯
    FI = 1048576
    RD = 2097152
    LastMod = 4194304
    FreeModAllowed = NF | EZ | HD | HR | SD | FL | \
                     FI | RX | AP | SO | keyMod       # ¯\_(ツ)_/¯
    Key9 = 16777216
    Key10 = 33554432
    Key1 = 67108864
    Key3 = 134217728
    Key2 = 268435456

    @classmethod
    def list_mods(cls, bitwise: int):
        """ Return a list of mod enums from the given bitwise (enabled_mods in the osu! API) """
        bin_str = str(bin(bitwise))[2:]
        bin_list = [int(d) for d in bin_str[::-1]]
        mods_bin = (pow(2, i) for i, d in enumerate(bin_list) if d == 1)
        mods = [cls(mod) for mod in mods_bin]

        # Manual checks for multiples
        if Mods.DT and Mods.NC in mods:
            mods.remove(Mods.DT)

        return mods

    @classmethod
    def format_mods(cls, mods):
        """ Return a string with the mods in a sorted format, such as DTHD.

        mods is either a bitwise or a list of mod enums. """
        if type(mods) is int:
            mods = cls.list_mods(mods)

        assert type(mods) is list

        if mods:
            sorted_mods = sorted((mod.name for mod in mods), key=str.lower)
        else:
            sorted_mods = ["Nomod"]

        return "".join(sorted_mods)


def def_section(api_name: str, first_element: bool=False):
    """ Add a section using a template to simplify adding API functions. """
    @asyncio.coroutine
    def template(**params):
        global requests_sent

        if "k" not in params:
            params["k"] = api_key

        # Download using a URL of the given API function name
        json = yield from utils.download_json(api_url + api_name, **params)
        requests_sent += 1

        # Unless we want to extract the first element, return the entire object (usually a list)
        if not first_element:
            return json

        # If the returned value should be the first element, see if we can cut it
        if len(json) < 1:
            return None

        return json[0]

    # Set the correct name of the function and add simple docstring
    template.__name__ = api_name
    template.__doc__ = "Get " + ("list" if not first_element else "dict") + " using " + api_url + api_name
    return template


# Define all osu! API requests using the template
get_beatmaps = def_section("get_beatmaps")
get_user = def_section("get_user", first_element=True)
get_scores = def_section("get_scores")
get_user_best = def_section("get_user_best")
get_user_recent = def_section("get_user_recent")
get_match = def_section("get_match", first_element=True)
get_replay = def_section("get_replay")


def get_beatmap(beatmaps: list, **lookup):
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
