""" This plugin is designed for various image utility ccommands.

Commands:
    resize """
import re
from collections import namedtuple
from io import BytesIO

from PIL import Image
import discord

import plugins
from pcbot import utils

try:
    from .emoji import get_emote, get_emoji, emote_regex
except:
    url_only = True
else:
    url_only = False


client = plugins.client  # type: discord.Client

extension_regex = re.compile(r"image/(?P<ext>\w+)(?:\s|$)")
ImageArg = namedtuple("ImageArg", "object format")


@plugins.argument("{open}url" + ("" if url_only else " or emoji") + "{suffix}{close}", pass_message=True)
async def image(message: discord.Message, url_or_emoji: str):
    """ Parse a url or emoji and return an ImageArg object. """
    # Check if the given string is a url and save the headers for later
    try:
        headers = await utils.retrieve_headers(url_or_emoji)
    except ValueError:  # Not a valid url, figure out if we support emoji
        assert not url_only, "`{}` **is not a valid URL.**".format(url_or_emoji)

        # There was no image to get, so let's see if it's an emoji
        char = "-".join(hex(ord(c))[2:] for c in url_or_emoji)  # Convert to a hex string
        image_object = get_emoji(char, size=256)
        if image_object:
            return ImageArg(object=image_object, format="PNG")

        # Not an emoji, so perhaps it's an emote
        match = emote_regex.match(url_or_emoji)
        if match:
            image_object = await get_emote(match.group("id"), message)
            if image_object:
                return ImageArg(object=image_object, format="PNG")

        # Alright, we're out of ideas
        raise AssertionError("`{}` **is neither a URL or an emoji.**".format(url_or_emoji))

    # The URL was valid so let's make sure it's an image
    match = extension_regex.search(headers["CONTENT-TYPE"])
    assert match, "**The given URL is not an image.**"

    # Download the image and create the object
    image_bytes = BytesIO(await utils.download_file(url_or_emoji))
    image_object = Image.open(image_bytes)
    image_format = match.group("ext")
    return ImageArg(object=image_object, format=image_format)


@plugins.argument("{open}width{suffix}{close}x{open}height{suffix}{close}")
def parse_resolution(res: str):
    """ Parse a resolution string. """
    # Show help when the format is incorrect
    if not res.count("x") == 1:
        return None

    # Try parsing the numbers in the resolution
    x, y = res.split("x")
    try:
        x = int(x)
        y = int(y)
    except ValueError:
        return None

    # Assign a maximum and minimum size
    if not (1 <= x <= 3000 and 1 <= y <= 3000):
        raise AssertionError("**Width and height must be between 1 and 3000.**")

    return x, y


def clean_format(image_format: str, extension: str):
    """ Return working options of JPG images. """
    if extension.lower() == "jpeg":
        extension = "jpg"
    if image_format.lower() == "jpg":
        image_format = "JPEG"

    return extension, image_format


async def send_image(channel: discord.Channel, image_object: Image, filename: str, format: str):
    """ Send an image. """
    try:
        image_fp = utils.convert_image_object(image_object, format)
    except KeyError as e:
        await client.send_message(channel, "Image format `{}` is unsupported.".format(e))
    except Exception as e:
        await client.send_message(channel, str(e) + ".")
    else:
        await client.send_file(channel, image_fp, filename=filename)


@plugins.command(pos_check=lambda s: s.startswith("-"))
async def resize(message: discord.Message, image_arg: image, resolution: parse_resolution, *options,
                 extension: str=None):
    """ Resize an image with the given resolution formatted as `<width>x<height>`
    with an optional extension. """
    # Set the image upload format, extension and filename
    image_format, extension = clean_format(image_arg.format, image_arg.format.lower() or extension)
    filename = "{}.{}".format(message.author.display_name, extension)

    # Resize the image
    image_object = image_arg.object.resize(resolution, Image.NEAREST if "-nearest" in options else Image.ANTIALIAS)

    # Upload the image
    await send_image(message.channel, image_object, filename, image_format)


@plugins.command(pos_check=lambda s: s.startswith("-"), aliases="tilt")
async def rotate(message: discord.Message, image_arg: image, degrees: int, *options, extension: str=None):
    """ Rotate an image clockwise using the given degrees. """
    # Set the image upload format, extension and filename
    image_format, extension = clean_format(image_arg.format, image_arg.format.lower() or extension)
    filename = "{}.{}".format(message.author.display_name, extension)

    # Rotate the image
    image_object = image_arg.object.rotate(-degrees, Image.NEAREST if "-nearest" in options else Image.BICUBIC,
                                           expand=True)

    # Upload the image
    await send_image(message.channel, image_object, filename, image_format)
