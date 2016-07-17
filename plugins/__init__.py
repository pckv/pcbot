""" PCBOT's plugin handler.
"""

import importlib
import os
import logging
import inspect
from collections import namedtuple, defaultdict
from functools import partial, wraps
from traceback import format_exc

import asyncio

from pcbot.utils import Annotate, format_exception

plugins = {}
events = defaultdict(list)
Command = namedtuple("Command", "name name_prefix usage description function parent sub_commands depth hidden error "
                                "pos_check disabled_pm")
lengthy_annotations = (Annotate.Content, Annotate.CleanContent, Annotate.LowerContent,
                       Annotate.LowerCleanContent, Annotate.Code)


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


def _format_usage(func, pos_check):
    """ Parse and format the usage of a command. """
    signature = inspect.signature(func)
    usage = []

    for i, param in enumerate(signature.parameters.values()):
        if i in (0, 1):
            continue

        # If there is a placeholder annotation, this command is a group and should not have a formatted usage
        if getattr(param.annotation, "__name__", "") == "placeholder":
            return

        param_format = getattr(param.annotation, "argument", "{open}{name}{suffix}{close}")
        name = param.name
        open, close, suffix = "[", "]", ""

        if param.default is param.empty and (param.kind is not param.VAR_POSITIONAL or pos_check is True):
            open, close = "<", ">"

        if param.kind is param.VAR_POSITIONAL or param.annotation in lengthy_annotations:
            suffix = " ..."

        usage.append(param_format.format(open=open, close=close, name=name, suffix=suffix))
    else:
        return " ".join(usage)


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
        # The prefix might have changed since the bot started because of mess
        from pcbot.config import command_prefix

        if not asyncio.iscoroutine(func):
            func = asyncio.coroutine(func)

        # Define all function stats
        name = options.get("name", func.__name__)
        hidden = options.get("hidden", False)
        parent = options.get("parent", None)
        depth = parent.depth + 1 if parent is not None else 0
        name_prefix = parent.name_prefix + " " + name if parent is not None else command_prefix + name
        error = options.get("error", None)
        pos_check = options.get("pos_check", False)
        description = options.get("description") or func.__doc__ or "Undocumented."
        disabled_pm = options.get("disabled_pm", False)

        formatted_usage = options.get("usage", _format_usage(func, pos_check))
        if formatted_usage is not None:
            usage = "{pre} {usage}".format(pre=name_prefix, usage=formatted_usage)
        else:
            usage = None

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
        cmd = Command(name=name, usage=usage, name_prefix=name_prefix, description=description, function=func,
                      parent=parent, sub_commands=[], depth=depth, hidden=hidden, error=error, pos_check=pos_check,
                      disabled_pm=disabled_pm)

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


def argument(format):
    """ Decorator for easily setting custom argument usage formats. """
    def decorator(func):
        func.argument = format
        return func

    return decorator


def parent_attr(cmd: Command, attr: str):
    """ Return the attribute from the parent if there is one. """
    return getattr(cmd.parent, attr, False) or getattr(cmd, attr)


def get_command(plugin, cmd: str):
    """ Find and return a command function from a plugin.

    :param plugin: plugin module to look through.
    :param cmd: a str representing the command name. """
    commands = getattr(plugin, "__commands", None)

    # Return None if the bot doesn't have any commands
    if not commands:
        return None

    names = [cmd.name for cmd in plugin.__commands]

    # Return None if the specified plugin doesn't have the specified command
    if cmd not in names:
        return None

    # Return the found command
    return commands[names.index(cmd)]


def get_sub_command(cmd, args: list):
    """ Go through all arguments and return any group command function.

    :param cmd: type plugins.Command
    :param args: a list of arguments *following* the command trigger. """
    for arg in args:
        names = [cmd.name for cmd in cmd.sub_commands]

        if not names:
            break

        if arg in names:
            cmd = cmd.sub_commands[names.index(arg)]

    return cmd


def load_plugin(name: str, package: str="plugins"):
    """ Load a plugin with the name name. If package isn't specified, this
    looks for plugin with specified name in /plugins/

    Any loaded plugin is imported and stored in the self.plugins dictionary. """
    if not name.startswith("__") or not name.endswith("__"):
        try:
            plugin = importlib.import_module("{package}.{plugin}".format(plugin=name, package=package))
        except ImportError as e:
            logging.error("An error occurred when loading plugin {}:\n{}".format(name, format_exception(e)))
            return False
        except:
            logging.error("An error occurred when loading plugin {}:\n{}".format(name, format_exc()))
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
        logging.debug("Reloaded plugin {}".format(name))


def unload_plugin(name: str):
    """ Unload a plugin by removing it from the plugin dictionary. """
    if name in plugins:
        del plugins[name]
        logging.debug("Unloaded plugin {}".format(name))


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
            except:
                logging.error("An error occurred when saving plugin {}:\n{}".format(name, format_exc()))


@asyncio.coroutine
def save_plugins():
    """ Looks for any save function in a plugin and saves.
    Set up for saving on !stop and periodic saving every 30 minutes. """
    for name in all_keys():
        yield from save_plugin(name)
