""" This plugin has some emoji to PNG utilities!

    Keep in mind that this library requires pycario, which I've found to be quite
    difficult to install for windows. """

import os

import discord
import cairosvg
import PIL

import plugins
from pcbot import Annotate


emoji_path = "plugins/twemoji21lib/"
size = 512


# This will be a list of all emoji SVG files. store this in
# RAM is for easier access. Considering the library of emojies
# only take up about 2.5MB (or 4MB in disk) as of now, and if
# the library expands, the size should not increase drastically.
emoji = {}
for file in os.listdir(emoji_path):
    with open(os.path.join(emoji_path, file), "rb") as f:
        emoji_name = file.split(".")[0]  # Strip the extension
        emoji_bytes = f.read()

        # Since the emojies specify no width/height by default, we'll add this to our SVG files in RAM.
        size_bytes = bytes(str(size), encoding="utf-8")
        emoji_bytes = emoji_bytes.replace(b"<svg ",
                                          b"<svg width=\"" + size_bytes + b"px\" height=\"" + size_bytes + b"px\" ")
        emoji[emoji_name] = emoji_bytes


@plugins.command()
def greater(client: discord.Client, message: discord.Message, text: Annotate.CleanContent):
    """ Gives a HUGE version of an emoji. """
    unicode = [hex(ord(c))[2:] for c in text]
    assert unicode[0] in emoji, "This is not an emoji."

    converted = cairosvg.svg2png(emoji[unicode[0]])
    yield from client.send_file(message.channel, converted, filename="{}.png".format(unicode[0]))
