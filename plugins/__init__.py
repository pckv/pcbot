import importlib
import os
import logging
import inspect

import asyncio

from bot import command_prefix
from pcbot import utils

plugins = {}


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


def command(usage=""):
    """ Decorator function that adds a command to the module's __commands dict.
    This allows the user to dynamically create commands without the use of a dictionary
    in the module itself.

    If no usage is specified, the builtin help command will not display help for this command. """
    def decorator(func):
        # Command function name needs to start with cmd_
        if not func.__name__.startswith("cmd_"):
            raise Exception("Command functions require the cmd_ prefix as the command name")

        name = func.__name__[4:]
        plugin = inspect.getmodule(func)
        commands = getattr(plugin, "__commands", {})

        # Assert that __commands is usable and that this command doesn't already exist
        if type(commands) is not dict:
            raise Exception("__commands is reserved for the plugin's commands, and must be of type dict")

        if name in commands:
            raise Exception("You can't assign two commands with the same name")

        # Update the __commands dictionary
        commands[name] = "{prefix}{name} {usage}".format(prefix=command_prefix, name=name, usage=usage)
        setattr(plugin, "__commands", commands)

        return func

    return decorator


def load_plugin(name: str, package: str="plugins"):
    """ Load a plugin with the name name. This plugin has to be
    situated under plugins/

    Any loaded plugin is imported and stored in the self.plugins dictionary. """
    if not name.startswith("__") or not name.endswith("__"):
        try:
            plugin = importlib.import_module("{package}.{plugin}".format(plugin=name, package=package))
        except ImportError as e:
            logging.warn("COULD NOT LOAD PLUGIN " + name + "\n" + utils.format_exception(e))
            return False

        plugins[name] = plugin
        logging.debug("LOADED PLUGIN " + name)
        return True

    return False


def reload_plugin(name: str):
    """ Reload a plugin. """
    if plugins.get(name):
        delattr(plugins[name], "__commands")  # Remove all registered plugins
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
