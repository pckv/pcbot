from enum import IntEnum


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
    keyMod = Key4 | Key5 | Key6 | Key7 | Key8
    FI = 1048576
    RD = 2097152
    LastMod = 4194304
    FreeModAllowed = NF | EZ | HD | HR | SD | FL | \
                     FI | RX | AP | SO | keyMod
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
        :param mods: either a bitwise or a list of mod enums. """
        if type(mods) is int:
            mods = cls.list_mods(mods)

        assert type(mods) is list
        if mods:
            sorted_mods = sorted((mod.name for mod in mods), key=str.lower)
        else:
            sorted_mods = ["Nomod"]

        return "".join(sorted_mods)
