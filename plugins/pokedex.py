""" Plugin that would act as a pokédex, specifically designed for Pokémon GO.

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
    resize = False
    logging.warn("PIL could not be loaded. The pokedex works like usual, however with lower resolution sprites.")
else:
    resize = True


api_path = "plugins/pokedexlib/pokedex.json"
sprites_path = "plugins/pokedexlib/sprites/"
pokedex_config = Config("pokedex", data=defaultdict(dict))
default_scale_factor = 1.8
min_scale_factor, max_scale_factor = 0.25, 4

# Load the Pokedex API
with open(api_path) as api_file:
    pokedex = json.load(api_file)

# Load all our sprites into RAM (they don't take much space)
# Unlike the pokedex.json API, these use pokemon ID as keys.
# The values are the sprites in bytes.
sprites = {}
for file in os.listdir(sprites_path):
    with open(os.path.join(sprites_path, file), "rb") as sprite_bytes:
        sprites[int(file.split(".")[0])] = sprite_bytes.read()


def id_to_name(pokemon_id: int):
    """ Convert the pokemon ID to a name. """
    for name, pokemon in pokedex.items():
        if pokemon["id"] == pokemon_id:
            return name

    return None


def resize_sprite(sprite, factor: float):
    """ Resize a sprite (string of bytes / rb). """
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
    """ Replaces -m and -f with ♂ and ♀ respectively. """
    return s.replace("-m", "♂").replace("-f", "♀")


@plugins.command(name="pokedex")
def pokedex_(client: discord.Client, message: discord.Message, name_or_id: Annotate.LowerCleanContent):
    """ Display some information of the given pokémon. """
    # Do some quick replacements
    if name_or_id.startswith("#"):
        name_or_id = name_or_id.replace("#", "")
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

    # Get the server's scale factor
    if message.server.id in pokedex_config.data and "scale-factor" in pokedex_config.data[message.server.id]:
        scale_factor = pokedex_config.data[message.server.id]["scale-factor"]
    else:
        scale_factor = default_scale_factor

    # Assign our pokemon
    pokemon = pokedex[name]

    # Assign the sprite to use
    if pokemon["id"] in sprites:
        sprite = sprites[pokemon["id"]]
    else:
        sprite = sprites[0]

    # Resize (if PIL is enabled) and upload the sprite
    if resize and not round(scale_factor, 2) == 1:
        sprite = resize_sprite(sprite, scale_factor)
    yield from client.send_file(message.channel, sprite, filename="{}.png".format(name))

    # Format Pokemon GO specific info
    pokemon_go_info = ""
    if "evolution_cost" in pokemon:
        pokemon_go_info += "Evolution cost: `{} {} Candy`\n".format(
            pokemon["evolution_cost"],
            replace_sex_suffix(pokemon["evolution"][0][0]).capitalize()  # Name of the first pokemon in its chain
        )
    if "hatches_from" in pokemon:
        pokemon_go_info += "Hatches from: `{}km Egg`\n".format(pokemon["hatches_from"])

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
        formatted_evolution=" **->** ".join(" **/** ".join(replace_sex_suffix(name).upper() for name in names)
                                            for names in pokemon["evolution"]),
        pokemon_go=pokemon_go_info,
        **pokemon
    )

    yield from client.say(message, formatted_message)


@permission("manage_server")
@pokedex_.command()
def scalefactor(client: discord.Client, message: discord.Message, factor: float=default_scale_factor):
    """ Set the scaling factor for your server. If no factor is given, the default is set. /
    **This command requires the `Manage Server` permission.**"""
    assert factor <= max_scale_factor, "The factor **{}** is too high **(max={})**.".format(
        factor, max_scale_factor)
    assert min_scale_factor <= factor, "The factor **{}** is too low **(min={})**.".format(
        factor, min_scale_factor)

    # Handle specific scenarios
    if factor == default_scale_factor:
        if "scale-factor" in pokedex_config.data[message.server.id]:
            del pokedex_config.data[message.server.id]["scale-factor"]
            reply = "Pokédex image scale factor reset to **{factor}**."
        else:
            reply = "Pokédex image scale factor is **{factor}**."
    else:
        pokedex_config.data[message.server.id]["scale-factor"] = factor
        reply = "Pokédex image scale factor set to **{factor}**."

    pokedex_config.save()
    yield from client.say(message, reply.format(factor=factor))
