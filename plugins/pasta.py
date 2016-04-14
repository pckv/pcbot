""" Script for copypastas

Commands:
!pasta
"""

from random import choice
# from re import match, search
# from io import BytesIO

import discord
import asyncio

import bot
from pcbot import Config
# from pcbot import download_file


commands = {
    "pasta": {
        "usage": "!pasta <copypasta | action>\n"
                 "Actions:\n"
                 "    --add <pastaname> <pasta>\n"
                 "    --remove <pastaname>\n"
                 "    -list [page]",
        "desc": "Use copypastas. Don't forget to enclose the copypasta in quotes: `\"pasta goes here\"` for multiline"
                "pasta action. You also need quotes around a `pastaname` if it has any spaces."
    }
}

pastas = Config("pastas", data={})
page_size = 150


@asyncio.coroutine
def on_message(client: bot.Bot, message: discord.Message, args: list):
    """ Here I'm using on_message instead of on_command in order to allow pastas
    to be triggered by the | notation. """
    if args[0] == "!pasta" or args[0].startswith("|"):
        if args[0].startswith("|"):
            org = args
            args = ["!pasta", org[0][1:]]
            args.extend(org[1:])
            asyncio.async(client.delete_message(message))
        if len(args) > 1:
            # List copypastas
            if args[1] == "-list":
                page = 1
                pasta_names = list(pastas.data.keys())

                if len(args) > 2:
                    try:
                        page = int(args[2])
                    except ValueError:
                        page = 1

                pasta_pages = []

                # Divide pasta_names into list of pages
                for i, pasta_name in enumerate(pasta_names):
                    p = int(i / page_size)  # Current page number

                    if i % page_size == 0:
                        pasta_pages.append([])

                    pasta_pages[p].append(pasta_name)

                # Don't go over page nor under
                page = len(pasta_pages) if page > len(pasta_pages) else 1

                m = "**Pastas (page {0}/{1}):** ```\n{2}\n```\n" \
                    "Use `!pasta -list [page]` to view another page.".format(page,
                                                                             len(pasta_pages),
                                                                             "\n".join(pasta_pages[page - 1]))

            # Add a copypasta
            elif args[1] == "--add":
                if len(args) > 3:
                    pasta_name = args[2].lower()
                    pasta = " ".join(args[3:])
                    if not pastas.data.get(pasta_name):
                        pastas.data[pasta_name] = pasta
                        pastas.save()
                        m = "Pasta `{}` set.".format(pasta_name)
                    else:
                        m = "Pasta `{0}` already exists. " \
                            "You can remove it with `!pasta --remove {0}`".format(pasta_name)
                else:
                    m = "Please follow the format of `!pasta --add <pastaname> <copypasta ...>`"

            # Remove a pasta
            elif args[1] == "--remove":
                if len(args) > 2:
                    pasta_name = " ".join(args[2:]).lower()
                    pasta = pastas.data.get(pasta_name)
                    if pasta:
                        pastas.data.pop(pasta_name)
                        pastas.save()
                        m = "Pasta `{}` removed. In case this was a mistake, here's the pasta: ```{}```".format(
                            pasta_name, pasta
                        )
                    else:
                        m = "No pasta by name `{}`.".format(pasta_name)
                else:
                    m = "Please specify a pasta to remove. `!pasta --remove <pastaname>`"

            # Retrieve and send pasta
            else:
                if pastas.data:
                    if args[1] == ".":
                        m = choice(list(pastas.data.values()))
                    else:
                        m = pastas.data.get(" ".join(args[1:]).lower()) or \
                            "Pasta `{0}` is undefined. " \
                            "Define with `!pasta --add \"{0}\" <copypasta ...>`".format(" ".join(args[1:]))
                else:
                    m = "There are no defined pastas. Define with `!pasta --add <pastaname> <copypasta ...>`"

                # Download and send the image if m is a link to an image (png, jpg, etc) although not gifs
                # if match(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", m):
                #     # TODO: Integrate aiohttp, disabled uploading for now.
                #     # Get the headers for the link before downloading the file
                #     request_head = requests.head(m)
                #     content_type = request_head.headers["content-type"]
                #
                #     if request_head.ok and content_type.startswith("image") and "gif" not in content_type:
                #         asyncio.async(client.send_typing(message.channel))  # Send typing to the channel
                #         request = requests.get(m)
                #
                #         file = BytesIO(request.content)
                #         filename = m
                #
                #         if "content-disposition" in request.headers:
                #             if "filename" in request.headers["content-disposition"]:
                #                 filename_match = search("filename=\"(?P<filename>\S+)\"",
                #                                         request.headers["content-disposition"])
                #                 if filename_match:
                #                     filename = filename_match.group("filename")
                #
                #         ext_match = match(r"^\S+\.(?P<ext>[a-zA-Z0-9]+)$", filename)
                #
                #         if ext_match:
                #             yield from client.send_file(message.channel, file,
                #                                         filename="image.{}".format(ext_match.group("ext")))
                #             m = None

        # No arguments
        else:
            m = "Please see `!help pasta`."

        if m:
            yield from client.send_message(message.channel, m)

        return True

    return False
