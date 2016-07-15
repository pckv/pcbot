""" Plugin that would act as a pokédex, specifically designed for Pokemon GO.

Commands:
    pokedex
"""

from io import BytesIO
import os

import discord
import json
from PIL import Image

import plugins


api_path = "plugins/pokedexlib//pokedex.json"
sprites_path = "plugins/pokedexlib/sprites/{id}.png"


with open(api_path) as f:
    pokedex = json.load(f)


def id_to_name(pokemon_id: int):
    """ Convert the pokemon ID to a name. """
    for name, pokemon in pokedex.items():
        if pokemon["id"] == pokemon_id:
            return name

    return None


def upscale_sprite(sprite, factor: float=2.2):
    """ Upscales a sprite (string of bytes / rb). """
    image = Image.open(BytesIO(sprite))

    # Resize with the scaled proportions
    width, height = image.size
    width, height = int(width * factor), int(height * factor)

    image = image.resize((width, height), Image.NEAREST)

    # Return the byte-like object
    buffer = BytesIO()
    image.save(buffer, "PNG")
    buffer.seek(0)
    return buffer


@plugins.command(name="pokedex")
def pokedex_(client: discord.Client, message: discord.Message, name_or_id: str.lower):
    """ Display some information on the given pokémon. """
    # Get the requested pokemon name
    name = name_or_id
    try:
        pokemon_id = int(name_or_id)
    except ValueError:
        assert name in pokedex, "There is no pokémon with that name in my pokédex!"
    else:
        name = id_to_name(pokemon_id)
        assert name is not None, "There is no pokémon of that ID in my pokédex!"

    # Assign our pokemon
    pokemon = pokedex[name]

    # Find the image to use
    sprite_path = sprites_path.format(id=pokemon["id"])
    if not os.path.exists(sprite_path):
        sprite_path = sprites_path.format(id=0)

    # Open said image
    with open(sprite_path, "rb") as f:
        sprite_bytes = f.read()

    # Upscale and upload the image
    sprite_bytes = upscale_sprite(sprite_bytes)
    yield from client.send_file(message.channel, sprite_bytes, filename="{}.png".format(name))

    # Format the message
    formatted_message = (
        "**#{id:03} {upper_name}**\n"
        "Weight: `{weight}kg` Height: `{height}m`\n"
        "Type: {type}\n"
        "**{genus} Pokémon**\n"
        "```\n{description}```"
        "**EVOLUTION**: {formatted_evolution}"
    ).format(
        upper_name=pokemon["name"].upper(),
        type=" | ".join(t.capitalize() for t in pokemon["types"]),
        formatted_evolution=" **->** ".join(" **/** ".join(name.upper() for name in names)
                                            for names in pokemon["evolution"]),
        **pokemon
    )

    yield from client.say(message, formatted_message)
