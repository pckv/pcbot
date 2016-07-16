""" Plugin that would act as a pokédex, specifically designed for Pokemon GO.

Commands:
    pokedex
"""

import os
import logging
from io import BytesIO
from collections import defaultdict

import discord
import json

import plugins
from pcbot import Config, permission, Annotate

try:
    from PIL import Image
except:
    upscale = False
    logging.warn("PIL could not be loaded. The pokedex works like usual, however with lower resolution sprites.")
else:
    upscale = True


api_path = "plugins/pokedexlib//pokedex.json"
sprites_path = "plugins/pokedexlib/sprites/{id}.png"
pokedex_config = Config("pokedex", data=defaultdict(dict))
default_upscale_factor = 1.8
min_upscale_factor, max_upscale_factor = 0.25, 4


with open(api_path) as f:
    pokedex = json.load(f)


def id_to_name(pokemon_id: int):
    """ Convert the pokemon ID to a name. """
    for name, pokemon in pokedex.items():
        if pokemon["id"] == pokemon_id:
            return name

    return None


def upscale_sprite(sprite, factor: float):
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


def replace_sex_suffix(s: str):
    return s.replace("-m", "♂").replace("-f", "♀")


@plugins.command(name="pokedex")
def pokedex_(client: discord.Client, message: discord.Message, name_or_id: Annotate.LowerCleanContent):
    """ Display some information on the given pokémon. """
    # Do some quick replacements
    name_or_id = name_or_id.replace("♂", "-m").replace("♀", "-f")
    name_or_id = name_or_id.replace(" ", "-").replace("♂", "m").replace("♀", "f")

    # Get the requested pokemon name
    name = name_or_id
    try:
        pokemon_id = int(name_or_id)
    except ValueError:
        assert name in pokedex, "There is no pokémon called **{}** in my pokédex!".format(name)
    else:
        name = id_to_name(pokemon_id)
        assert name is not None, "There is no pokémon with ID **#{:03}** in my pokédex!".format(pokemon_id)

    # Get the server's upscale factor
    if "upscale-factor" in pokedex_config.data[message.server.id]:
        upscale_factor = pokedex_config.data[message.server.id]["upscale-factor"]
    else:
        upscale_factor = default_upscale_factor

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
    if upscale:
        sprite_bytes = upscale_sprite(sprite_bytes, upscale_factor)
    yield from client.send_file(message.channel, sprite_bytes, filename="{}.png".format(name))

    # Format Pokemon GO specific info
    pokemon_go_info = ""
    if "evolution_cost" in pokemon:
        pokemon_go_info += "Evolution cost: `{} {} Candy`\n".format(
            pokemon["evolution_cost"],
            replace_sex_suffix(pokemon["evolution"][0][0]).capitalize()  # Name of the first pokemon in its chain
        )
    if "hatches_from" in pokemon:
        pokemon_go_info += "Hatches from: `{}km egg`\n".format(pokemon["hatches_from"])

    # Format the message
    formatted_message = (
        "**#{id:03} {upper_name}**\n"
        "Weight: `{weight}kg` Height: `{height}m`\n"
        "Type: `{type}`\n"
        "**{genus} Pokémon**\n"
        "{pokemon_go}"
        "```\n{description}```"
        "**EVOLUTION**: {formatted_evolution}"
    ).format(
        upper_name=replace_sex_suffix(pokemon["name"]).upper(),
        type=" | ".join(t.capitalize() for t in pokemon["types"]),
        formatted_evolution=" **->** ".join(" **/** ".join(name.upper() for name in names)
                                            for names in pokemon["evolution"]),
        pokemon_go=pokemon_go_info,
        **pokemon
    )

    yield from client.say(message, formatted_message)


@permission("manage_server")
@pokedex_.command()
def setupscale(client: discord.Client, message: discord.Message, factor: float=default_upscale_factor):
    """ Set the upscale factor for your server. If no factor is given, the default is set. /
    **This command requires the `Manage Server` permission.**"""
    assert factor <= max_upscale_factor, "The factor **{}** is too high **(max={})**.".format(
        factor, max_upscale_factor)
    assert min_upscale_factor <= factor, "The factor **{}** is too low **(min={})**.".format(
        factor, min_upscale_factor)

    # Handle specific scenarios
    if factor == default_upscale_factor:
        if "upscale-factor" in pokedex_config.data[message.server.id]:
            del pokedex_config.data[message.server.id]["upscale-factor"]
            reply = "Pokédex image upscale factor reset to **{factor}**."
        else:
            reply = "Pokédex image upscale factor is **{factor}**."
    else:
        pokedex_config.data[message.server.id]["upscale-factor"] = factor
        reply = "Pokédex image upscale factor set to **{factor}**."

    pokedex_config.save()
    yield from client.say(message, reply.format(factor=factor))
