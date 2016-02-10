import logging
import os
import random
import shlex
import importlib
from datetime import datetime
from getpass import getpass
from sys import exit

import discord
import asyncio

from pcbot.config import Config

logging.basicConfig(level=logging.INFO)
plugins = {}


def load_plugins():
    for plugin in os.listdir("plugins/"):
        plugin_name = os.path.splitext(plugin)[0]
        if not plugin_name.startswith("__") or not plugin_name.endswith("__"):
            plugins[plugin_name] = importlib.import_module("plugins.{}".format(plugin_name))


def reload_plugin(plugin_name):
    if plugins.get(plugin_name):
        plugins[plugin_name] = importlib.reload(plugins[plugin_name])


class Bot(discord.Client):
    def __init__(self):
        super().__init__()
        self.message_count = Config("count")
        self.owner = Config("owner")

        load_plugins()

    def is_owner(self, user):
        if type(user) is not str:
            user = user.id

        if user == self.owner.data:
            return True

        return False

    @asyncio.coroutine
    def on_ready(self):
        print('Logged in as')
        print(self.user.name)
        print(self.user.id)
        print('------')

    @asyncio.coroutine
    def on_message(self, message: discord.Message):
        if message.author == self.user:
            return

        # Log every command to console (logs anything starting with !)
        if message.content.startswith("!"):
            logging.log(logging.INFO, "{0}@{1.author.name}: {1.content}".format(
                datetime.now().strftime("%d.%m.%y %H:%M:%S"),
                message
            ))

        # Split content into arguments by space (surround with quotes for spaces)
        args = shlex.split(message.content)

        # Below are all owner specific commands
        if message.channel.is_private and message.content == "!setowner":
            if self.owner.data:
                yield from self.send_message(message.channel, "An owner is already set.")
                return

            owner_code = str(random.randint(100, 999))
            print("Owner code for assignment: {}".format(owner_code))
            yield from self.send_message(message.channel,
                                         "A code has been printed in the console for you to repeat within 15 seconds.")
            user_code = yield from self.wait_for_message(timeout=15, content=owner_code)
            if user_code:
                yield from self.send_message(message.channel, "You have been assigned bot owner.")
                self.owner.data = message.author.id
                self.owner.save()
            else:
                yield from self.send_message(message.channel, "You failed to send the desired code.")

        if self.is_owner(message.author):
            # Stops the bot
            if message.content == "!stop":
                bot.logout()
                exit("Stopped by owner.")

            # Sets the bots game
            elif args[0] == "!game":
                if len(args) > 1:
                    game = discord.Game(name=args[1])
                    logging.log(logging.DEBUG, "Setting bot game to {}".format(args[1]))
                    yield from self.change_status(game)
                else:
                    yield from self.send_message(message.channel, "Usage: `!game <game>`")

            # Plugin specific commands
            elif args[0] == "!plugin":
                if len(args) > 1:
                    if args[1] == "reload":
                        if len(args) > 2:
                            if plugins.get(args[2]):
                                reload_plugin(args[2])
                                yield from self.send_message(message.channel, "Reloaded plugin `{}`".format(args[2]))
                            else:
                                yield from self.send_message(message.channel,
                                                             "`{}` is not a plugin. Use `!plugins`".format(args[2]))
                        else:
                            for plugin in plugins.items():
                                reload_plugin(plugin)
                            yield from self.send_message(message.channel, "All plugins reloaded.")
                    else:
                        yield from self.send_message(message.channel, "`{}` is not a valid argument.".format(args[1]))
                else:
                    yield from self.send_message(message.channel,
                                                 "Plugins: ```{}```".format("\n,".join(plugins.keys())))

            # Originally just a test command
            elif message.content == "!count":
                if not self.message_count.data.get(message.channel.id):
                    self.message_count.data[message.channel.id] = 0

                self.message_count.data[message.channel.id] += 1
                yield from self.send_message(message.channel, "I have counted `{}` times in this channel.".format(
                    self.message_count.data[message.channel.id]
                ))
                self.message_count.save()

        # Run plugins on_message
        for name, plugin in plugins.items():
            yield from plugin.on_message(self, message, args)


bot = Bot()

if __name__ == "__main__":
    email = input("Email: ")
    password = getpass()
    bot.run(email, password)
