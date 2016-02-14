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

            for i in range(1, 6):
                reply = yield from client.wait_for_message(timeout=120, channel=message.channel,
                                                           check=lambda m: m.content.lower() == "i")
                if reply:
                    yield from client.send_message(message.channel, "{} has entered!".format(reply.author.mention))
                    participants.append(reply.author.id)
                else:
                    yield from client.send_message(message.channel, "**The Russian Roulette game failed to gather "
                                                                    "6 participants.**")
                    return

            # Set random order of participants and add one bullet
            participants = shuffle(participants)
            bullets = [False] * 6
            bullets[randint(1, 6)] = True

            for i, participant in enumerate(participants):
                member = message.server.get_member(participant)

                yield from client.send_message(message.channel,
                                               "{} is up next! Say `go` whenever you are ready.".format(member.mention))
                _ = yield from client.wait_for_message(timeout=60, channel=message.channel,
                                                       check=lambda m: "go" in m.content.lower())

                hit = ":dash:"

                if bullets[i]:
                    hit = ":boom:"

                yield from client.send_message(message.channel, "{} {} :gun: ".format(member.mention, hit))

                if bullets[i]:
                    yield from client.send_message(message.channel, "**GAME OVER**")
                    break

        else:
            yield from client.send_message(message.channel, "This channel is already playing Russian Roulette.")
