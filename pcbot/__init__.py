""" this module is the PCBOT specific module, containing helpers
and the default plugin with default commands.

This module does not load the builtin plugin as that is handled by
the plugin manager (plugins.__init__.py)
"""

from .config import *
from .utils import *
from .cleverbot import Cleverbot
