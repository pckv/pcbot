""" This plugin has some emoji to PNG utilities!

Keep in mind that this library requires pycario, which I've found to be quite
difficult to install for windows.

Commands:
    greater
"""

import os
import re
from io import BytesIO

import discord
import cairosvg
from PIL import Image

import plugins
from pcbot import Annotate


emoji_path = "plugins/twemoji21lib/"
default_size = 512
max_width = default_size * 4
max_emoji = 64
emoji = {}


def init_emoji():
    """ This will be a list of all emoji SVG files. Storing this in RAM is for
    easier access, considering the library of emojies only take up about 2.5MB
    (or 4MB in disk) as of now. If the library expands, the size should not
    increase drastically. """
    for file in os.listdir(emoji_path):
        with open(os.path.join(emoji_path, file), "rb") as f:
            emoji_name = file.split(".")[0]  # Strip the extension
            emoji_bytes = f.read()
            emoji[emoji_name] = emoji_bytes


def get_emoji(chars: str, size=default_size):
    """ Return the emoji with the specified character and optionally
    with the given size. """
    if chars not in emoji:
        return None

    emoji_bytes = emoji[chars]
    size_bytes = bytes(str(size), encoding="utf-8")
    emoji_bytes = emoji_bytes.replace(b"<svg ",
                                      b"<svg width=\"" + size_bytes + b"px\" height=\"" + size_bytes + b"px\" ")
    return cairosvg.svg2png(emoji_bytes)


def parse_emoji(text: str):
    """ Go through and return all emoji in the given string. """
    parsed_emoji = []

    # Convert all characters in the given text to hex format strings
    chars = [hex(ord(c))[2:] for c in text if not c == " "]
    chars_remaining = length = len(chars)

    # Try the entire string backwards, and reduce the length by one character until there'text a match
    while True:
        sliced_chars = chars[:length]

        # If the emoji is in the list, update the index and reset the length, with the updated index
        if "-".join(sliced_chars) in emoji.keys():
            parsed_emoji.append("-".join(sliced_chars))
            chars = chars[length:]
            chars_remaining = length = len(chars)
            continue

        # When we don't find an emoji, reduce the length
        length -= 1

        # When the length is 0, but the amount of characters is greater than 1, remove the first one
        if length == 0 and chars_remaining > 1:
            chars = chars[1:]
            chars_remaining = length = len(chars)
        elif length < 1:
            break

    size = default_size

    # When the size of all emoji next to each other is greater than the max width,
    # divide the size to properly fit the max_width at all times
    if size * len(parsed_emoji) > max_width:
        scale = 1 / ((size * len(parsed_emoji) - 1) // max_width + 1)
        size *= scale

    return [get_emoji(c, size=size) for c in parsed_emoji]


@plugins.command()
def greater(client: discord.Client, message: discord.Message, text: Annotate.CleanContent):
    """ Gives a **huge** version of emojies. """
    # Parse all unicode and load the emojies
    parsed_emoji = parse_emoji(text)
    assert parsed_emoji, "I couldn't find any emoji in that text of yours."

    # We now want to combine the images if there are multiples
    # If there is no need to combine the images, send just the one
    if len(parsed_emoji) == 1:
        yield from client.send_file(message.channel, parsed_emoji[0], filename="emoji.png")
        return

    image_objects = [Image.open(BytesIO(b)) for b in parsed_emoji]
    size, _ = image_objects[0].size
    width, height = size * len(image_objects), size

    # Stitch all the images together
    image = Image.new("RGBA", (width, height))
    for i, image_object in enumerate(image_objects):
        image.paste(image_object, box=(i * default_size, 0))

    # Upload the stitched image
    buffer = BytesIO()
    image.save(buffer, "PNG")
    buffer.seek(0)
    yield from client.send_file(message.channel, buffer, filename="emojies.png")


init_emoji()

