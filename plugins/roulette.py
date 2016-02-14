""" Script for Russian Roulette

Commands: none
"""

from random import randint, shuffle

import discord
import asyncio

commands = {
    "roulette": {
        "usage": "!roulette",
        "desc": "Starts a game of Russian Roulette. To participate, say `I` in the chat.\n"
                "Please beware that you may or may not die using this command."
    }
}

# List containing all channels running !roulette
started = []


@asyncio.coroutine
def on_message(client: discord.Client, message: discord.Message, args: list):
    if args[0].lower() == "!roulette":
        if message.channel.id not in started:
            started.append(message.channel.id)

            yield from client.send_message(message.channel,
                                           "{} has started a game of Russian Roulette! To participate,"
                                           " say `I`! 6 players needed.".format(message.author.mention))

            # List containing participant user ids
            participants = []

            for i in range(6):
                def check(m):
                    if m.content.lower() == "i" and m.author.id not in participants:
                        return True

                    return False

                reply = yield from client.wait_for_message(timeout=10, channel=message.channel, check=check)

                if reply:
                    yield from client.send_message(message.channel,
                                                   "{} has entered! `{}/6`".format(reply.author.mention, i+1))
                    participants.append(reply.author.id)
                else:
                    yield from client.send_message(message.channel, "**The Russian Roulette game failed to gather "
                                                                    "6 participants.**")
                    started.pop(started.index(message.channel.id))

                    return

            # Set random order of participants and add one bullet
            shuffle(participants)
            bullets = [0] * 6
            bullets[randint(0, 5)] = 1

            for i, participant in enumerate(participants):
                member = message.server.get_member(participant)

                yield from client.send_message(message.channel,
                                               "{} is up next! Say `go` whenever you are ready.".format(member.mention))
                _ = yield from client.wait_for_message(timeout=60, channel=message.channel, author=member,
                                                       check=lambda m: "go" in m.content.lower())

                hit = ":dash:"

                if bullets[i] == 1:
                    hit = ":boom:"

                yield from client.send_message(message.channel, "{} {} :gun: ".format(member.mention, hit))

                if bullets[i] == 1:
                    break

            started.pop(started.index(message.channel.id))
            yield from client.send_message(message.channel, "**GAME OVER**")

        else:
            yield from client.send_message(message.channel, "This channel is already playing Russian Roulette.")
