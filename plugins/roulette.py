""" Script for Russian Roulette

Commands:
!roulette
"""

from random import randint, choice
from threading import Timer

import discord
import asyncio

commands = {
    "roulette": {
        "usage": "!roulette [participants]",
        "desc": "Starts a game of Russian Roulette. To participate, say `I` in the chat.\n"
                "The optional `participants` argument sets a custom number of participants.\n"
                "Please beware that you may or may not die using this command."
    }
}

# List containing all channels running !roulette
started = []


class Roulette:
    name = "Russian Roulette"
    min_num = 1

    def __init__(self, client: discord.Client, message: discord.Message, num: int):
        self.client = client
        self.message = message
        self.member = message.server.get_member(client.user.id)

        self.num = num if num >= self.min_num else self.min_num
        self.participants = []
        self.bullets = []

    def on_start(self):
        m = "{} has started a game of {}! To participate, say `I`! {} players needed.".format(
            self.message.author.mention, self.name, self.num)

        yield from self.client.send_message(self.message.channel, m)

    def get_participants(self):
        for i in range(self.num):
            def check(m):
                if m.content.lower().strip() == "i" and m.author.id not in self.participants:
                    return True

                return False

            reply = yield from self.client.wait_for_message(timeout=120, channel=self.message.channel, check=check)

            if reply:
                asyncio.async(
                    self.client.send_message(self.message.channel,
                                             "{} has entered! `{}/{}`. "
                                             "Type `I` to join!".format(reply.author.mention, i+1, self.num)))
                self.participants.append(reply.author.id)
                if self.member.permissions_in(self.message.channel).manage_messages:
                    asyncio.async(self.client.delete_message(reply))
            else:
                yield from self.client.send_message(self.message.channel,
                                                    "**The {} game failed to gather"
                                                    " {} participants.**".format(
                                                        self.name, self.num
                                                    ))
                started.pop(started.index(self.message.channel.id))

                return False

    def shuffle(self):
        self.bullets = [0] * len(self.participants)
        self.bullets[randint(0, len(self.participants)-1)] = 1

    def game(self):
        for i, participant in enumerate(self.participants):
            member = self.message.server.get_member(participant)

            yield from self.client.send_message(
                self.message.channel,
                "{} is up next! Say `go` whenever you are ready.".format(member.mention)
            )
            reply = yield from self.client.wait_for_message(timeout=15, channel=self.message.channel, author=member,
                                                            check=lambda m: "go" in m.content.lower())

            hit = ":dash:"

            if self.bullets[i] == 1 or reply is None:
                hit = ":boom:"

            if reply is None:
                yield from self.client.send_message(self.message.channel, "*fuck you*")

            yield from self.client.send_message(self.message.channel, "{} {} :gun: ".format(member.mention, hit))

            if self.bullets[i] == 1:
                break

        yield from self.client.send_message(self.message.channel, "**GAME OVER**")

        started.pop(started.index(self.message.channel.id))

    def start(self):
        yield from self.on_start()
        valid = yield from self.get_participants()
        if valid is not False:
            self.shuffle()
            yield from self.game()


class HotPotato(Roulette):
    name = "Hot Potato"
    min_num = 3

    def __init__(self, client: discord.Client, message: discord.Message, num: int):
        super().__init__(client, message, num)

        self.time_remaining = 0

        del self.bullets

    def shuffle(self):
        pass

    def timer(self):
        self.time_remaining -= 1
        if self.time_remaining > 0:
            Timer(1, self.timer).start()

    def game(self):
        self.time_remaining = randint(
            int(pow(7 * len(self.participants), 0.8)),
            int(pow(15 * len(self.participants), 0.8))
        )

        participant = choice(self.participants)
        Timer(1, self.timer).start()
        reply = True
        pass_to = [choice(self.participants), choice(self.participants)]

        while self.time_remaining > 0:
            member = self.message.server.get_member(participant)
            if pass_to[0] == member.id:
                while member.id in pass_to:
                    pass_to = [choice(self.participants), choice(self.participants)]

            if reply is not None:
                yield from self.client.send_message(
                    self.message.channel,
                    "{} :bomb: got the bomb! Pass it to either {} or {}!".format(
                        member.mention,
                        self.message.server.get_member(pass_to[0]).mention,
                        self.message.server.get_member(pass_to[1]).mention
                    )
                )

            def check(m):
                if len(m.mentions) > 0:
                    if m.mentions[0].id in pass_to:
                        return True

                return False

            wait = (self.time_remaining - 5) if (self.time_remaining >= 5) else self.time_remaining
            reply = yield from self.client.wait_for_message(timeout=wait, channel=self.message.channel, author=member,
                                                            check=check)

            if reply:
                participant = reply.mentions[0].id
                pass_to = [member.id]
            elif self.time_remaining == 5:
                asyncio.async(self.client.send_message(self.message.channel, ":bomb: :fire: **IT'S GONNA BLOW!**"))

        yield from self.client.send_message(self.message.channel, "{} :fire: :boom: :boom: :fire:".format(
            self.message.server.get_member(participant).mention
        ))
        yield from self.client.send_message(self.message.channel, "**GAME OVER**")

        started.pop(started.index(self.message.channel.id))


@asyncio.coroutine
def on_message(client: discord.Client, message: discord.Message, args: list):
    if args[0].lower() == "!roulette":
        if message.channel.id not in started:
            started.append(message.channel.id)
            num = 6

            if len(args) > 1:
                try:
                    num = int(args[1])
                except ValueError:
                    num = 6

            if num < 1:
                num = 6

            roulette = Roulette(client, message, num)

            yield from roulette.start()
        else:
            yield from client.send_message(message.channel, "**This channel is already playing.**")

    if args[0].lower() == "!hotpotato":
        if message.channel.id not in started:
            started.append(message.channel.id)
            num = 6

            if len(args) > 1:
                try:
                    num = int(args[1])
                except ValueError:
                    num = 6

            if num < 1:
                num = 6

            hot_potato = HotPotato(client, message, num)

            yield from hot_potato.start()
        else:
            yield from client.send_message(message.channel, "**This channel is already playing.**")
