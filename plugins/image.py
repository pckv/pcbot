""" This plugin is designed for various image utility ccommands.

Commands:
    resize"""
import re
from io import BytesIO

from PIL import Image
import discord

import plugins
from pcbot import utils


extension_regex = re.compile(r"image/(?P<ext>\w+)(?:\s|$)")


@plugins.argument("{open}width{suffix}{close}x{open}height{suffix}{close}")
def parse_resolution(res: str):
    """ Parse a resolution string. """
    if not res.count("x") == 1:
        return None

    x, y = res.split("x")
    try:
        x = int(x)
        y = int(y)
    except ValueError:
        return None

    if not (1 <= x <= 3000 and 1 <= y <= 3000):
        return None

    return x, y


@plugins.command(pos_check=lambda s: s.startswith("-"))
async def resize(client: discord.Client, message: discord.Message,
                 url: str, resolution: parse_resolution, *options, extension: str=None):
    """ Resize an image with the given resolution formatted as `<width>x<height>`
    with an optional extension. """
    # Make sure the URL is valid
    try:
        headers = await utils.retrieve_headers(url)
    except ValueError:
        await client.say(message, "The given URL is invalid.")
        return

    match = extension_regex.search(headers["CONTENT-TYPE"])
    assert match, "The given url is not an image."

    image_bytes = await utils.download_file(url)

    # Create some metadata
    image_format = extension or match.group("ext")

    # Set the image upload extension
    extension = image_format.lower()
    if extension.lower() == "jpeg":
        extension = "jpg"
    if image_format.lower() == "jpg":
        image_format = "JPEG"

    filename = "{}.{}".format(message.author.display_name, extension)

    # Open the image in Pillow
    image = Image.open(image_bytes)
    image = image.resize(resolution, Image.NEAREST if "-nearest" in options else Image.ANTIALIAS)

    # Upload the image
    buffer = BytesIO()
    try:
        image.save(buffer, image_format)
    except KeyError as e:
        await client.say(message, "Image format `{}` is unsupported.".format(e))
        return
    except Exception as e:
        await client.say(message, str(e) + ".")
        return
    buffer.seek(0)

    await client.send_file(message.channel, buffer, filename=filename)
