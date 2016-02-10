""" Script for basic commands

Commands:
!hello
"""

import discord


async def on_message(client: discord.Client, message: discord.Message, args: list):
    if args[0] == "!ping":
        await client.send_message(message.channel, "pong")
    elif args[0] == "!cool":
        await client.send_message(message.channel, "Do you think I'm cool? (reply yes, no or maybe)")
        reply = await client.wait_for_message(timeout=30, author=message.author, channel=message.channel)

        if reply:
            if reply.content.lower() == "yes":
                await client.send_message(message.channel, "I think you are cool too. :sunglasses:")
            elif reply.content.lower() == "no":
                await client.send_message(message.channel, "Well I disagree. :thumbsdown:")
            elif reply.content.lower() == "maybe":
                await client.send_message(message.channel, "What kind of answer is that? :zzz:")
            else:
                await client.send_message(message.channel, "I don't get it. :frowning:")
