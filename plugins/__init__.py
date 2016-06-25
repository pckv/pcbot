""" PCBOT's plugin handler.
"""

import importlib
import os
import logging
import inspect
from collections import namedtuple, defaultdict
from functools import partial

import asyncio

from pcbot import utils, command_prefix

plugins = {}
events = defaultdict(list)
Command = namedtuple("Command", "name usage description function sub_commands parent hidden error pos_check")


def get_plugin(name):
    """ Return the loaded plugin by name or None. """
    if name in plugins:
        return plugins[name]

    return None


def all_items():
    """ Return a view object of every loaded plugin by key, value. """
    return plugins.items()


def all_keys():
    """ Return a view object of every loaded plugin by key. """
    return plugins.keys()


def all_values():
    """ Return a view object of every loaded plugin by value. """
    return plugins.values()


def command(**options):
    """ Decorator function that adds a command to the module's __commands dict.
    This allows the user to dynamically create commands without the use of a dictionary
    in the module itself.

    Command attributes are:
        name        : str         : The commands name. Will use the function name by default.
        usage       : str         : The command usage following the command trigger, e.g the "[cmd]" in "help [cmd]".
        description : str         : The commands description. By default this uses the docstring of the function.
        hidden      : bool        : Whether or not to show this function in the builtin help command.
        error       : str         : An optional message to send when argument requirements are not met.
        pos_check   : func / bool : An optional check function for positional arguments, eg: pos_check=lambda s: s
                                    When this attribute is a bool and True, force positional arguments.
    """
    def decorator(func):
        if not asyncio.iscoroutine(func):
            func = asyncio.coroutine(func)

        # Define all function stats
        name = options.get("name", func.__name__)
        hidden = options.get("hidden", False)
        parent = options.get("parent", None)
        error = options.get("error", None)
        pos_check = options.get("pos_check", False)
        description = options.get("description") or func.__doc__ or "Undocumented."
        usage = None

        if not parent:
            usage = "{pre}{name} {usage}".format(
                pre=command_prefix, name=name, usage=options.get("usage", ""))

        # Properly format description when using docstrings
        # Kinda like markdown; new line = (blank line) or (/ at end of line)
        if description == func.__doc__:
            new_desc = ""

            for line in description.split("\n"):
                line = line.strip()

                if line.endswith("/"):
                    new_desc += line[:-1] + "\n"
                elif line == "":
                    new_desc += "\n\n"
                else:
                    new_desc += line + " "

            description = new_desc

        # Format the description for any optional keys
        description = description.format(pre=command_prefix)

        # Load the plugin the function is from, so that we can modify the __commands attribute
        plugin = inspect.getmodule(func)
        commands = getattr(plugin, "__commands", list())

        # Assert that __commands is usable and that this command doesn't already exist
        if type(commands) is not list:
            raise NameError("__commands is reserved for the plugin's commands, and must be of type list")

        # Assert that there are no commands already defined with the given name
        if any(cmd.name == name for cmd in commands):
            raise KeyError("You can't assign two commands with the same name")

        # Create our command
        cmd = Command(name=name, usage=usage, description=description, function=func, parent=parent,
                      sub_commands=[], hidden=hidden, error=error, pos_check=pos_check)

        # If the command has a parent (is a subcommand)
        if parent:
            parent.sub_commands.append(cmd)
        else:
            commands.append(cmd)

        # Update the plugin's __commands attribute
        setattr(plugin, "__commands", commands)

        # Create a command attribute for the command function that automatically assigns the parent
        setattr(func, "command", partial(command, parent=cmd))

        logging.debug("Registered {} {} from plugin {}".format("subcommand" if parent else "command",
                                                               name, plugin.__name__))
        return func

    return decorator


def event(name=None):
    """ Decorator to add event listeners in plugins. """
    def decorator(func):
        if name == "on_ready":
            raise NameError("on_ready in plugins is reserved for bot initialization only (use it without the"
                            "event listener call).")

        if not asyncio.iscoroutine(func):
            func = asyncio.coroutine(func)

        # Register our event
        event_name = name or func.__name__
        events[event_name].append(func)
        return func

    return decorator


def parent_attr(cmd: Command, attr: str):
    """ Return the attribute from the parent if there is one. """
    return getattr(cmd.parent, attr, False) or getattr(cmd, attr)


def load_plugin(name: str, package: str="plugins"):
    """ Load a plugin with the name name. If package isn't specified, this
    looks for plugin with specified name in /plugins/

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
    if name in plugins:
        # Remove all registered commands
        if hasattr(plugins[name], "__commands"):
            delattr(plugins[name], "__commands")

        # Remove all registered events from the given plugin
        for event_name, funcs in events.items():
            for func in funcs:
                if func.__module__ == "plugins." + name:
                    events[event_name].remove(func)

        plugins[name] = importlib.reload(plugins[name])
        logging.debug("RELOADED PLUGIN " + name)


def unload_plugin(name: str):
    """ Unload a plugin by removing it from the plugin dictionary. """
    if name in plugins:
        del plugins[name]
        logging.debug("UNLOADED PLUGIN " + name)


def load_plugins():
    """ Perform load_plugin(name) on all plugins in plugins/ """
    if not os.path.exists("plugins/"):
        os.mkdir("plugins/")

    for plugin in os.listdir("plugins/"):
        name = os.path.splitext(plugin)[0]

        if not name.endswith("lib"):  # Exclude libraries
            load_plugin(name)


@asyncio.coroutine
def save_plugin(name):
    """ Save a plugin's files if it has a save function. """
    if name in all_keys():
        plugin = get_plugin(name)

        if callable(getattr(plugin, "save", False)):
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
