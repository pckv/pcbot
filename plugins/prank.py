""" Prank plugin

This plugin returns an image, pranking a user.

For on_message(), args is a list of all arguments split with shlex.

Commands:
!prank
"""

import discord
import asyncio
from PIL import Image, ImageDraw, ImageFont

commands = {
    "prank": {
        "usage": "!prank [user]",
        "desc": "Prank your favourite user!\n"
                "`user` is optional and will specify the user. This is either a @mention, username (will detect users) "
                "or whatever you'd like."
    }
}

prank_path = "plugins/prank/"

image_base = Image.open(prank_path + "discord_prank.png").convert("RGBA")
image_width, image_height = image_base.size


@asyncio.coroutine
def on_message(client: discord.Client, message: discord.Message, args: list):
    if args[0] == "!prank":
        name = "IT'S A"

        # Set the name and convert any mention to name (this ignores punctuation and converts "@PC," to "PC")
        if len(args) > 1 and len(message.clean_content) < 200:
            name_list = []

            for arg in args[1:]:
                steps = 3 if len(args) == 2 else 1
                member = client.find_member(message.server, arg, steps=steps)

                if member:
                    name_list.append(member.name)
                else:
                    channel = client.find_channel(message.server, arg, steps=0)

                    if channel:
                        name_list.append(channel.name)
                    else:
                        name_list.append(arg)

            name = " ".join(name_list)

        name = name.upper()

        # Initialize the image anhd font
        image_text = Image.new("RGBA", image_base.size, (255, 255, 255, 0))
        image_font = ImageFont.truetype(prank_path + "American Captain.ttf", 50)
        image_context = ImageDraw.Draw(image_text)

        # Set width and height and scale down when necessary
        width, height = image_context.textsize(name, image_font)
        font_size = 50

        if width > image_width:
            scaled_font = None

            while width > image_width:
                scaled_font = ImageFont.truetype(prank_path + "American Captain.ttf", font_size)
                width, height = image_context.textsize(name, scaled_font)
                font_size -= 1

            image_font = scaled_font

        # Set x and y coordinates for centered text
        x = (image_width - width) / 2
        y = (image_height - height / 2) - image_height / 1.3

        # Draw border
        shadow_offset = font_size // 25
        image_context.text((x-shadow_offset, y), name, font=image_font, fill=(0, 0, 0, 255))
        image_context.text((x+shadow_offset, y), name, font=image_font, fill=(0, 0, 0, 255))
        image_context.text((x, y-shadow_offset), name, font=image_font, fill=(0, 0, 0, 255))
        image_context.text((x, y+shadow_offset), name, font=image_font, fill=(0, 0, 0, 255))

        # Draw text
        image_context.text((x, y), name, font=image_font, fill=(255, 255, 255, 255))

        # Combine the base image with the font image
        image = Image.alpha_composite(image_base, image_text)

        # Save and send the image
        image.save(prank_path + "pranked.png")
        yield from client.send_file(message.channel, prank_path + "pranked.png")
