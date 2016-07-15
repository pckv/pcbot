""" This plugin has some emoji to PNG utilities!

    Keep in mind that this library requires pycario, which I've found to be quite
    difficult to install for windows. """

import os
from io import BytesIO

import discord
import cairosvg
from PIL import Image

import plugins
from pcbot import Annotate


emoji_path = "plugins/twemoji21lib/"
size = 512
max_width = size * 4
max_emoji = 64


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

# This cache will store any PNG file for this session
emoji_cache = {}


@plugins.command()
def greater(client: discord.Client, message: discord.Message, text: Annotate.CleanContent):
    """ Gives a **huge** version of emojies. """
    # Convert the given text to characters
    unicode = [hex(ord(c))[2:] for c in text]
    
    # Parse all unicode and load the emojies
    parsed_emoji = []
    combined = False
    for i, char in enumerate(unicode):
        if len(parsed_emoji) > max_emoji:
            break

        if combined:
            combined = False
            continue

        # Some emojies use two unicode characters, so we try to parse these first
        if len(unicode) > (i + 1):
            name = "{}-{}".format(char, unicode[i + 1])

            if name in emoji:
                if name not in emoji_cache:
                    converted = cairosvg.svg2png(emoji[name])
                    emoji_cache[name] = converted
                else:
                    converted = emoji_cache[name]
                
                parsed_emoji.append(converted)
                combined = True
                continue

        # At this point we only need one character, and we pretty much do the entire process over again
        # (I know, this code is pretty lame)
        if char in emoji:
            if char not in emoji_cache:
                converted = cairosvg.svg2png(emoji[char])
                emoji_cache[char] = converted
            else:
                converted = emoji_cache[char]

            parsed_emoji.append(converted)

    assert parsed_emoji, "I couldn't find any emoji in that text of yours."

    # We now want to combine the images if there are multiples
    # If there is no need to combine the images, send just the one
    if len(parsed_emoji) == 1:
        yield from client.send_file(message.channel, parsed_emoji[0], filename="emoji.png")
        return

    image_objects = [Image.open(BytesIO(b)) for b in parsed_emoji]
    width, height = size * len(image_objects), size

    # Stitch all the images together
    image = Image.new("RGBA", (width, height))
    for i, image_object in enumerate(image_objects):
        image.paste(image_object, box=(i * size, 0))

    # Resize the image so that the width is no higher than 2048, but only for each factor 
    # we go higher than the max_width
    if width > max_width:
        scale = 1 / ((width - 1) // max_width + 1)
        image = image.resize((int(width * scale), int(height * scale)), Image.ANTIALIAS)

    # Upload the stitched image
    buffer = BytesIO()
    image.save(buffer, "PNG")
    buffer.seek(0)
    yield from client.send_file(message.channel, buffer, filename="emojies.png")

