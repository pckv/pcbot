""" Script for Russian Roulette

Commands: none
"""

from random import randint, shuffle

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

            yield from client.send_message(message.channel,
                                           "{} has started a game of Russian Roulette! To participate,"
                                           " say `I`! {} players needed.".format(message.author.mention, num))

            # List containing participant user ids
            participants = []

            for i in range(num):
                def check(m):
                    if m.content.lower() == "i" and m.author.id not in participants:
                        return True

                    return False

                reply = yield from client.wait_for_message(timeout=120, channel=message.channel, check=check)

                if reply:
                    asyncio.async(
                        client.send_message(message.channel,
                                            "{} has entered! `{}/{}`. "
                                            "Type `I` to join!".format(reply.author.mention, i+1, num)))
                    participants.append(reply.author.id)
                    if message.server.get_member(client.user.id).permissions_in(message.channel).manage_messages:
                        asyncio.async(client.delete_message(reply))
                else:
                    yield from client.send_message(message.channel, "**The Russian Roulette game failed to gather "
                                                                    "{} participants.**".format(num))
                    started.pop(started.index(message.channel.id))

                    return

            # Set random order of participants and add one bullet
            # shuffle(participants)  # We don't want to shuffle the participants, necessarily
            bullets = [0] * num
            bullets[randint(0, num-1)] = 1

            for i, participant in enumerate(participants):
                member = message.server.get_member(participant)

                yield from client.send_message(message.channel,
                                               "{} is up next! Say `go` whenever you are ready.".format(member.mention))
                _ = yield from client.wait_for_message(timeout=60, channel=message.channel, author=member,
                                                       check=lambda m: "go" in m.content.lower())

                hit = ":dash:"

                if bullets[i] == 1 or _ is None:
                    hit = ":boom:"

                if _ is None:
                    yield from client.send_message(message.channel, "*fuck you*")

                yield from client.send_message(message.channel, "{} {} :gun: ".format(member.mention, hit))

                if bullets[i] == 1:
                    break

            started.pop(started.index(message.channel.id))
            yield from client.send_message(message.channel, "**GAME OVER**")

        else:
            yield from client.send_message(message.channel, "This channel is already playing Russian Roulette.")
