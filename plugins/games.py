""" Plugin for Russian Roulette

Commands:
    roulette
    hotpotato
"""

from datetime import datetime
from random import randint, choice
from threading import Timer

import asyncio
import discord

import plugins


# List containing all channels playing a game
started = []


class Game:
    name = "Unnamed Game"
    minimum_participants = 1

    def __init__(self, client: discord.Client, message: discord.Message, num: int):
        self.client = client
        self.message = message
        self.channel = message.channel
        self.member = message.server.me

        self.num = num if num >= self.minimum_participants else self.minimum_participants
        self.participants = []

    async def on_start(self):
        """ Notify the channel that the game has been initialized. """
        await self.client.say(self.message,
                                   "{} has started a game of {}! To participate, say `I`! {} players needed.".format(
                                       self.message.author.mention, self.name, self.num))

    async def get_participants(self):
        """ Wait for input and get all participants. """
        for i in range(self.num):
            def check(m):
                if m.content.lower().strip() == "i" and m.author.id not in self.participants:
                    return True

                return False

            # Wait with a timeout of 2 minutes and check each message with check(m)
            reply = await self.client.wait_for_message(timeout=120, channel=self.channel, check=check)

            if reply:  # A user replied with a valid check
                asyncio.ensure_future(
                    self.client.say(self.message,
                                    "{} has entered! `{}/{}`. Type `I` to join!".format(
                                        reply.author.mention, i + 1, self.num))
                )
                self.participants.append(reply.author.id)

                # Remove the message if bot has permissions
                if self.member.permissions_in(self.channel).manage_messages:
                    asyncio.ensure_future(self.client.delete_message(reply))
            else:
                # At this point we got no reply in time and thus, gathering participants failed
                await self.client.say(self.message, "**The {} game failed to gather {} participants.**".format(
                    self.name, self.num))
                started.pop(started.index(self.channel.id))

                return False

    async def prepare(self):
        """ Prepare anything needed before starting the game. """
        pass

    async def game(self):
        """ Start playing the game. """
        pass

    async def start(self):
        """ Run the entire game's cycle. """
        await self.on_start()
        valid = await self.get_participants()
        await asyncio.sleep(1)

        if valid is not False:
            await self.prepare()
            await self.game()


class Roulette(Game):
    """ A game of Roulette. """
    name = "Russian Roulette"

    def __init__(self, client: discord.Client, message: discord.Message, num: int):
        super().__init__(client, message, num)
        self.bullets = []

    async def prepare(self):
        """ Shuffle the bullets. """
        self.bullets = [0] * len(self.participants)
        self.bullets[randint(0, len(self.participants) - 1)] = 1

    async def game(self):
        """ Start playing. """
        for i, participant in enumerate(self.participants):
            member = self.message.server.get_member(participant)

            await self.client.send_message(
                self.channel,
                "{} is up next! Say `go` whenever you are ready.".format(member.mention)
            )
            reply = await self.client.wait_for_message(timeout=15, channel=self.channel, author=member,
                                                            check=lambda m: "go" in m.content.lower())

            hit = ":dash:"

            if self.bullets[i] == 1 or reply is None:
                hit = ":boom:"

            if reply is None:
                await self.client.send_message(self.channel, "*fuck you*")

            await self.client.send_message(self.channel, "{} {} :gun: ".format(member.mention, hit))

            if self.bullets[i] == 1:
                break

        await self.client.send_message(self.channel, "**GAME OVER**")

        started.pop(started.index(self.channel.id))


class HotPotato(Game):
    name = "Hot Potato"
    minimum_participants = 3

    def __init__(self, client: discord.Client, message: discord.Message, num: int):
        super().__init__(client, message, num)
        self.time_remaining = 0

    def timer(self):
        """ I honestly don't remember how this function works. """
        self.time_remaining -= 1
        if self.time_remaining > 0:
            Timer(1, self.timer).start()

    async def game(self):
        """ Start the game. No comments because I was stupid and now I'm too
        lazy to comment everything in. """
        self.time_remaining = randint(
            int(pow(14 * len(self.participants), 0.8)),
            int(pow(30 * len(self.participants), 0.8))
        )

        participant = choice(self.participants)
        Timer(1, self.timer).start()
        reply = True
        pass_to = []
        notify = randint(2, int(self.time_remaining / 2))

        while self.time_remaining > 0:
            member = self.message.server.get_member(participant)

            if not pass_to:
                pass_from = list(self.participants)
                pass_from.pop(pass_from.index(member.id))
                pass_to = [choice(pass_from)]
                pass_from.pop(pass_from.index(pass_to[0]))
                pass_to.append(choice(pass_from))

            if reply is not None:
                await self.client.send_message(
                    self.channel,
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

            wait = (self.time_remaining - notify) if (self.time_remaining >= notify) else self.time_remaining
            reply = await self.client.wait_for_message(timeout=wait, channel=self.channel, author=member,
                                                            check=check)

            if reply:
                participant = reply.mentions[0].id
                pass_to = []
                if self.member.permissions_in(self.channel).manage_messages:
                    asyncio.ensure_future(self.client.delete_message(reply))
            elif self.time_remaining == notify:
                asyncio.ensure_future(self.client.send_message(self.channel, ":bomb: :fire: **IT'S GONNA BLOW!**"))
                self.time_remaining -= 1

        await self.client.send_message(self.channel, "{} :fire: :boom: :boom: :fire:".format(
            self.message.server.get_member(participant).mention
        ))
        await self.client.send_message(self.channel, "**GAME OVER**")

        del started[started.index(self.channel.id)]


class Typing(Game):
    name = "Typing"
    sentences = ["I am PC.", "PC is me.", "How very polite to be a tree."]
    minimum_wpm = 35

    def __init__(self, client: discord.Client, message: discord.Message, num: int):
        super().__init__(client, message, num)
        self.sentence = ""

    async def prepare(self):
        """ Get the sentence to send. """
        self.sentence = choice(self.sentences)

    async def send_sentence(self):
        """ Generate the function for sending the sentence. """
        await self.client.send_message(self.channel, self.sentence)

    def calculate_accuracy(self, content: str):
        """ Calculate the accuracy """

    def calculate_wpm(self, content: str, delta_seconds: int):
        """ Calculate the gross WPM from the given timedelta.
        This function will return a wpm where any 5 characters is considered a word.

        :param delta_seconds: Seconds elapsed since start. """

        minutes = delta_seconds * 60

    def calculate_timeout(self):
        """ Calculate the timeout for this game. """
        words = self.sentence.split()

    async def game(self):
        """ Run the game. """
        started = datetime.now()


desc_template = "Starts a game of {game.name}. To participate, say `I` in the chat.\n\n" \
                "The optional `participants` argument sets a custom number of participants, where " \
                "`{game.minimum_participants}` is the minimum."


def init_game(client: discord.Client, message: discord.Message, game, num: int):
    """ Initialize a game.

    :param game: A Game object.
    :param num: The specified participants
    """
    if num > message.server.member_count:
        num = message.server.member_count

    # The channel should not be playing two games at once
    assert message.channel.id not in started, "**This channel is already playing.**"

    # Start the game
    started.append(message.channel.id)
    asyncio.ensure_future(game(client, message, num).start())


@plugins.command(description=desc_template.format(game=Roulette))
async def roulette(client: discord.Client, message: discord.Message, participants: int=6):
    """ The roulette command. Description is defined using a template. """
    init_game(client, message, Roulette, participants)


@plugins.command(description=desc_template.format(game=HotPotato))
async def hotpotato(client: discord.Client, message: discord.Message, participants: int=4):
    """ The hotpotato command. Description is defined using a template. """
    init_game(client, message, HotPotato, participants)
