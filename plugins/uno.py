""" Script for Uno

THIS SCRIPT IS NOT COMPLETE.

Commands are specified by name, with keys usage and desc:
commands = {
    "cmd": {
        "usage": "!cmd <arg>",
        "desc": "Is a command."
    }
}

For on_message(), args is a list of all arguments split with shlex.

Commands: none
"""

import random
from enum import Enum

import discord
import asyncio

commands = {

}

uno = {}


class Color(Enum):
    undefined = 1
    yellow = 2
    green = 3
    red = 4
    blue = 5


class Type(Enum):
    number = 1
    reverse = 2
    skip = 3
    draw_two = 4
    wild = 5
    wild_draw_four = 6


class Card:
    def __init__(self, card_type, color=Color.undefined, number=None):
        self.card_type = card_type
        self.color = color if (card_type is not Type.wild and card_type is not Type.wild_draw_four) else Color.undefined
        self.number = number if card_type is Type.number else None

        if self.number:
            if self.number > 9 or self.number < 0:
                self.number = None

    def set_color(self, c):
        if self.card_type is Type.wild or self.card_type is Type.wild_draw_four:
            self.color = c
            return True

        return False

    def text(self):
        text = self.color.name + " / "
        if self.number:
            text += str(self.number)
        else:
            text += self.card_type.name.replace("_", " ")

        return text

    def act(self):
        pass

    # Compare cards
    def __eq__(self, other):
        return self.color == other.color and self.card_type == other.card_type and self.number == other.number


class Deck:
    def __init__(self):
        self.cards = []

        # Add all color cards to the deck
        for name, color in Color.__members__.items():
            if color is not Color.undefined:
                self.cards.append(Card(Type.number, color, 0))
                for i in range(1, 10):
                    for _ in range(2):
                        self.cards.append(Card(Type.number, color, i))
                for _ in range(2):
                    self.cards.append(Card(Type.skip, color))
                    self.cards.append(Card(Type.reverse, color))
                    self.cards.append(Card(Type.draw_two, color))

        for _ in range(4):
            self.cards.append(Card(Type.wild))
            self.cards.append(Card(Type.wild_draw_four))

    def shuffle(self):
        random.shuffle(self.cards)

    def pick(self):
        if len(self.cards) > 1:
            card = self.cards[-1]
            self.cards.pop(-1)
            return card

        return None


deck = Deck()


@asyncio.coroutine
def on_command(client: discord.Client, message: discord.Message, args: list):
    global deck

    if args[0] == "!deck":
        deck = Deck()
        yield from client.send_message(message.channel, "Created new deck.")
    elif args[0] == "!shuffle":
        deck.shuffle()
        yield from client.send_message(message.channel, "Shuffled deck.")
    elif args[0] == "!pick":
        amount = 1

        if len(args) > 1:
            try:
                amount = int(args[1])
            except ValueError:
                amount = 1

        cards = deck.pick(amount=amount)

        m = "Cards picked: ```\n"

        for card in cards:
            m += "- " + card.text() + "\n"

        m += "```\nCards in deck: " + str(len(deck.cards))

        yield from client.send_message(message.channel, m)

    elif args[0] == "!uno":
        if not uno.get(message.server):
            uno[message.server] = {}

        uno[message.server]["players"] = [message.author]

        # Add all mentioned users to our list of participants
        if len(message.mentions) > 0:
            for member in message.mentions:
                if member not in uno[message.server]["players"]:
                    uno[message.server]["players"].append(member)
        else:
            yield from client.send_message(message.channel, "You need to add at least one player.")
            return

        uno[message.server]["channel"] = yield from client.create_channel(message.server, "uno")

        # Assign permissions for uno channel
        permission = discord.Permissions.none()
        permission.send_messages = True

        # Set up all personal deck channels (private message)
        for member in uno[message.server]["players"]:
            yield from client.send_message(member, "Welcome to your deck, {}!".format(member.mention))

        yield from client.edit_channel_permissions(uno[message.server]["channel"], message.server.default_role,
                                                   deny=permission)

        # Give players permission to write in the #uno channel
        for member in uno[message.server]["players"]:
            yield from client.edit_channel_permissions(uno[message.server]["channel"], member, allow=permission)

    elif args[0] == "!unostop":
        if uno.get(message.server, {}).get("channel"):
            yield from client.delete_channel(uno[message.server]["channel"])
