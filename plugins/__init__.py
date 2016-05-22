import importlib
import os
import logging
import inspect
from collections import namedtuple
from functools import partial

import asyncio

from pcbot import utils

plugins = {}
Command = namedtuple("Command", "name usage description function sub_commands parent hidden error pos_check")


def get_plugin(name):
    if name in plugins:
        return plugins[name]

    return None


def all_items():
    return plugins.items()


def all_keys():
    return plugins.keys()


def all_values():
    return plugins.values()


def command(**options):
    """ Decorator function that adds a command to the module's __commands dict.
    This allows the user to dynamically create commands without the use of a dictionary
    in the module itself.

    Command attributes are:
        name        : str   : The commands name. Will use the function name by default.
        usage       : str   : The command usage following the command trigger, e.g the `[cmd]` in `!help [cmd]`.
        description : str   : The commands description. By default this uses the docstring of the function.
        hidden      : bool  : Whether or not to show this function in the builtin help command.
        error       : str   : An optional message to send when argument requirements are not met.
        pos_check   : func  : An optional check function for positional arguments, eg: pos_check=lambda s: s
    """

    def decorator(func):
        if not asyncio.iscoroutine(func):
            func = asyncio.coroutine(func)

        # Define all function stats
        name = options.get("name", func.__name__)
        hidden = options.get("hidden", False)
        parent = options.get("parent", None)
        error = options.get("error", None)
        pos_check = options.get("pos_check", lambda s: s)
        description = options.get("description") or func.__doc__ or "Undocumented."

        if not parent:
            usage = "{prefix}{name} {usage}".format(prefix=utils.command_prefix,
                                                    name=name,
                                                    usage=options.get("usage", ""))
        else:
            usage = None

        # Properly format description when using docstrings
        if description == func.__doc__:
            description = "\n".join(s.strip() for s in description.split("\n"))

        # Load the plugin the function is from, so that we can modify the __commands attribute
        plugin = inspect.getmodule(func)
        commands = getattr(plugin, "__commands", list())

        # Assert that __commands is usable and that this command doesn't already exist
        if type(commands) is not list:
            raise Exception("__commands is reserved for the plugin's commands, and must be of type list")

        # Assert that there are no commands already defined with the given name
        if any(cmd.name == name for cmd in commands):
            raise Exception("You can't assign two commands with the same name")

        # Create our command
        cmd = Command(name=name,
                      usage=usage,
                      description=description,
                      function=func,
                      sub_commands=[],
                      parent=parent,
                      hidden=hidden,
                      error=error,
                      pos_check=pos_check)

        if parent:
            parent.sub_commands.append(cmd)
        else:
            commands.append(cmd)

        # Update the plugin's __commands attribute
        setattr(plugin, "__commands", commands)

        setattr(func, "command", partial(command, parent=cmd))
        logging.debug("Registered {} {} from plugin {}".format("subcommand" if parent else "command",
                                                               name, plugin.__name__))
        return func

    return decorator


def load_plugin(name: str, package: str = "plugins"):
    """ Load a plugin with the name name. This plugin has to be
    situated under plugins/

    Any loaded plugin is imported and stored in the self.plugins dictionary. """
    if not name.startswith("__") or not name.endswith("__"):
        try:
            plugin = importlib.import_module("{package}.{plugin}".format(plugin=name, package=package))
        except ImportError as e:
            logging.warn("COULD NOT LOAD PLUGIN {name}\n{e}".format(name=name, e=utils.format_exception(e)))
            return False

        plugins[name] = plugin
        logging.debug("LOADED PLUGIN " + name)
        return True

    return False


def reload_plugin(name: str):
    """ Reload a plugin. """
    if plugins.get(name):
        if hasattr(plugins[name], "__commands"):  # Remove all registered commands
            delattr(plugins[name], "__commands")
        plugins[name] = importlib.reload(plugins[name])
        logging.debug("RELOADED PLUGIN " + name)


def unload_plugin(name: str):
    """ Unload a plugin by removing it from the plugin dictionary. """
    if plugins.get(name):
        plugins.pop(name)
        logging.debug("UNLOADED PLUGIN " + name)


def load_plugins():
    """ Perform load_plugin(name) on all plugins in plugins/ """
    if not os.path.exists("plugins/"):
        os.mkdir("plugins/")

    for plugin in os.listdir("plugins/"):
        name = os.path.splitext(plugin)[0]

        if not name.endswith("lib"):  # Skip libraries
            load_plugin(name)


@asyncio.coroutine
def save_plugin(name):
    """ Save a plugin's files if it has a save function. """
    if name in all_keys():
        plugin = get_plugin(name)

        if getattr(plugin, "save", False):
            try:
                yield from plugin.save(plugins)
            except Exception as e:
                logging.error("An error occurred when saving plugin " + name + "\n" +
                              utils.format_exception(e))


@asyncio.coroutine
def save_plugins():
    """ Looks for any save function in a plugin and saves.
    Set up for saving on !stop and periodic saving every 30 minutes. """
    for name in all_keys():
        yield from save_plugin(name)
