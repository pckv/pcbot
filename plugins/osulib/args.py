""" Argument parser for pp options. """

import re
from collections import namedtuple

from .api import Mods


Argument = namedtuple("Argument", "pattern type default")
mods_names = re.compile(r"\w{2}")


class RegexArgumentParser:
    """ Create a simple orderless regex argument parser. """
    def __init__(self):
        self.arguments = {}

    def add(self, name, pattern, type, default=None):
        """ Adds an argument. The pattern must have a group. """
        self.arguments[name] = Argument(pattern=re.compile(pattern), type=type, default=default)

    def parse(self, *args):
        """ Parse arguments. """
        Namespace = namedtuple("Namespace", " ".join(self.arguments.keys()))
        _namespace = {name: arg.default for name, arg in self.arguments.items()}

        # Go through all arguments and find a match
        for user_arg in args:
            for name, arg in self.arguments.items():
                # Skip any already assigned arguments
                if _namespace[name] is not arg.default:
                    continue

                # Assign the arguments on match and break the lookup
                match = arg.pattern.match(user_arg)
                if match:
                    _namespace[name] = arg.type(match.group(1))
                    break

        # Return the complete Namespace namedtuple
        return Namespace(**_namespace)


def mods(s: str):
    """ Return a list of api.Mods from the given str. """
    names = mods_names.findall(s)
    mod_list = []

    # Find and add all identified mods
    for name in names:
        for mod in Mods:
            if mod.name.lower() == name.lower():
                mod_list.append(mod)
                break

    return mod_list


parser = RegexArgumentParser()
parser.add("acc", r"([0-9.]+)%", type=float, default=100.0)
parser.add("c300", r"(\d+)x300", type=int, default=0xFFFF)
parser.add("c100", r"(\d+)x100", type=int, default=0)
parser.add("c50", r"(\d+)x50", type=int, default=0)

parser.add("misses", r"(\d+)m", type=int, default=0)
parser.add("combo", r"(\d+)x", type=int, default=0xFFFF)
parser.add("mods", r"\+(\w+)", type=mods)
parser.add("score_version", r"scorev(\d)", type=int, default=1)

parser.add("ar", r"ar([0-9.]+)", type=float)
parser.add("cs", r"cs([0-9.]+)", type=float)
parser.add("od", r"od([0-9.]+)", type=float)

parser.add("pp", r"([0-9.]+)pp", type=float)


def parse(*args):
    """ Parse pp arguments. """
    return parser.parse(*args)
