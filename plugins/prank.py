""" Prank plugin

This plugin returns an image, pranking a user.

Commands:
    prank
"""
from io import BytesIO

import discord
from PIL import Image, ImageDraw, ImageFont

import bot
import plugins
from pcbot import Annotate

client = plugins.client  # type: bot.Client


prank_path = "plugins/pranklib/"
__commands = []

image_base = Image.open(prank_path + "discord_prank.png").convert("RGBA")
image_width, image_height = image_base.size


@plugins.command()
async def prank(message: discord.Message, phrase: Annotate.CleanContent="IT'S A"):
    """ Prank! """
    phrase = phrase.upper()

    # Initialize the image and font
    image_text = Image.new("RGBA", image_base.size, (255, 255, 255, 0))
    image_font = ImageFont.truetype(prank_path + "American Captain.ttf", 50)
    image_context = ImageDraw.Draw(image_text)

    # Set width and height and scale down when necessary
    width, height = image_context.textsize(phrase, image_font)
    font_size = 50

    if width > image_width:
        scaled_font = None

        while width > image_width:
            scaled_font = ImageFont.truetype(prank_path + "American Captain.ttf", font_size)
            width, height = image_context.textsize(phrase, scaled_font)
            font_size -= 1

        image_font = scaled_font

    # Set x and y coordinates for centered text
    x = (image_width - width) / 2
    y = (image_height - height / 2) - image_height / 1.3

    # Draw border
    shadow_offset = font_size // 25
    image_context.text((x - shadow_offset, y), phrase, font=image_font, fill=(0, 0, 0, 255))
    image_context.text((x + shadow_offset, y), phrase, font=image_font, fill=(0, 0, 0, 255))
    image_context.text((x, y - shadow_offset), phrase, font=image_font, fill=(0, 0, 0, 255))
    image_context.text((x, y + shadow_offset), phrase, font=image_font, fill=(0, 0, 0, 255))

    # Draw text
    image_context.text((x, y), phrase, font=image_font, fill=(255, 255, 255, 255))

    # Combine the base image with the font image
    image = Image.alpha_composite(image_base, image_text)

    # Upload the image
    buffer = BytesIO()
    image.save(buffer, "PNG")
    buffer.seek(0)
    await client.send_file(message.channel, buffer, filename="pranked.png")
