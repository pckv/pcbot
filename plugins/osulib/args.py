""" Argument parser for pp options. """

import re
from collections import namedtuple

from .api import Mods

Argument = namedtuple("Argument", "pattern kwarg_pattern type default")
mods_names = re.compile(r"\w{2}")
kwarg = r"{}=(?P<value>\S+)"


class RegexArgumentParser:
    """ Create a simple orderless regex argument parser. """
    def __init__(self):
        self.arguments = {}

    def add(self, name, pattern, type, default=None):
        """ Adds an argument. The pattern must have a group. """
        self.arguments[name] = Argument(pattern=re.compile(pattern, flags=re.IGNORECASE),
                                        kwarg_pattern=re.compile(kwarg.format(name)),
                                        type=type, default=default)

    def parse(self, *args):
        """ Parse arguments.

        :raise ValueError: An argument is invalid.
        """
        Namespace = namedtuple("Namespace", " ".join(self.arguments.keys()))
        _namespace = {name: arg.default for name, arg in self.arguments.items()}

        # Go through all arguments and find a match
        for user_arg in args:
            for name, arg in self.arguments.items():
                # Skip any already assigned arguments
                if _namespace[name] is not arg.default:
                    continue

                # Assign the arguments on match and break the lookup
                match = arg.pattern.fullmatch(user_arg, )
                if match:
                    _namespace[name] = arg.type(match.group(1))
                    break

                # Check for kwarg patterns (e.g acc=99.32 instead of 99.32%)
                match = arg.kwarg_pattern.fullmatch(user_arg)
                if match:
                    _namespace[name] = arg.type(match.group("value"))
                    break
            else:
                raise ValueError("{} is an invalid argument.".format(user_arg))

        # Return the complete Namespace namedtuple
        return Namespace(**_namespace)


def mods(s: str):
    """ Return a list of api.Mods from the given str. """
    names = mods_names.findall(s)
    mod_list = []

    # Find and add all identified mods
    for name in names:
        for mod in Mods:
            # Skip duplicate mods
            if mod in mod_list:
                continue

            if mod.name.lower() == name.lower():
                mod_list.append(mod)
                break

    return mod_list


parser = RegexArgumentParser()
parser.add("acc", r"([0-9.]+)%", type=float)
parser.add("c300", r"(\d+)x300", type=int)
parser.add("c100", r"(\d+)x100", type=int, default=0)
parser.add("c50", r"(\d+)x50", type=int, default=0)

parser.add("misses", r"(\d+)(?:m|xm(?:iss)?)", type=int, default=0)
parser.add("combo", r"(\d+)x", type=int)
parser.add("mods", r"\+(\w+)", type=mods)
parser.add("score_version", r"(?:score)?v([12])", type=int, default=1)

parser.add("ar", r"ar([0-9.]+)", type=float)
parser.add("cs", r"cs([0-9.]+)", type=float)
parser.add("od", r"od([0-9.]+)", type=float)
parser.add("hp", r"hp([0-9.]+)", type=float)

parser.add("hits", "(\d+)hits", type=int)
parser.add("pp", r"([0-9.]+)pp", type=float)

parser.add("rank", r"([SSH|SS|SH|S|A|B|C|D|F]rank)", type=str)

def parse(*args):
    """ Parse pp arguments. """
    return parser.parse(*args)
