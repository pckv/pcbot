""" Plugin that would act as a pokédex, specifically designed for Pokémon GO.

Commands:
    pokedex
"""

import os
import logging
from io import BytesIO
from collections import defaultdict
from operator import itemgetter
from difflib import get_close_matches

import discord
import json

import plugins
from pcbot import Config, permission, Annotate, command_prefix

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

pokemon_go_gen = [1]

# Load the Pokedex API
with open(api_path) as api_file:
    api = json.load(api_file)
    pokedex = api["pokemon"]

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


def egg_name(pokemon_evolution: list):
    """ Return the egg name of the pokemon_evolution chain. """
    # The pokemon are in their respective order, so we'll find the first one with
    # a Pokemon GO generation pokemon
    for names in pokemon_evolution:
        for name in names:
            pokemon = pokedex[name]

            if pokemon["generation"] in pokemon_go_gen:
                return pokemon["locale_name"]

    return "Unknown"


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


def format_type(types: list):
    """ Format a string from a list of a pokemon's types. """
    return " | ".join(t.capitalize() for t in types)


@plugins.command(name="pokedex", aliases="pd pokemon")
def pokedex_(client: discord.Client, message: discord.Message, name_or_id: Annotate.LowerCleanContent):
    """ Display some information of the given pokémon. """
    # Do some quick replacements for flexible parsing
    name_or_id = name_or_id.strip()

    if name_or_id.startswith("#"):
        name_or_id = name_or_id.replace("#", "")
    if " " in name_or_id:
        if "♀" in name_or_id or "♀" in name_or_id or name_or_id.endswith("f") or name_or_id.endswith("m"):
            name_or_id = name_or_id.replace(" ", "-").replace("♂", "m").replace("♀", "f")
        else:
            name_or_id = name_or_id.replace(" ", "")

    # Get the requested pokemon name
    name = name_or_id
    try:
        pokemon_id = int(name_or_id)
    except ValueError:
        # See if there's a pokemon with the locale name formatted like the given name
        for pokemon in pokedex.values():
            if pokemon["locale_name"].lower() == name:
                name = pokemon["name"]
                break

        # Correct the name if it is very close to an existing pokemon and there's only one close match
        matches = get_close_matches(name, pokedex.keys(), n=2, cutoff=0.8)
        if matches and len(matches) == 1:
            name = matches[0]

        assert name in pokedex, "There is no pokémon called **{}** in my pokédex!\nPerhaps you meant: `{}`?".format(
            name, ", ".join(get_close_matches(name, pokedex.keys(), cutoff=0.5)))
    else:
        name = id_to_name(pokemon_id)
        assert name is not None, "There is no pokémon with ID **#{:03}** in my pokédex!".format(pokemon_id)

    # Get the server's scale factor
    if not message.channel.is_private \
            and message.server.id in pokedex_config.data and "scale-factor" in pokedex_config.data[message.server.id]:
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
        pokemon_go_info += "Evolution cost: `{} {} Candy` ".format(
            pokemon["evolution_cost"], egg_name(pokemon["evolution"]))

    if "hatches_from" in pokemon:
        if pokemon_go_info:
            pokemon_go_info += "\n"
        pokemon_go_info += "Hatches from: `{}km Egg` ".format(pokemon["hatches_from"])

    if pokemon_go_info:
        pokemon_go_info = "**Pokémon GO**\n" + pokemon_go_info

    # Format the message
    formatted_message = (
        "**#{id:03} {upper_name} - GEN {generation}**\n"
        "Weight: `{weight}kg` Height: `{height}m`\n"
        "Type: `{type}`\n"
        "**{genus} Pokémon**\n"
        "{pokemon_go}"
        "```\n{description}```"
        "**EVOLUTION**: {formatted_evolution}"
    ).format(
        upper_name=pokemon["locale_name"].upper(),
        type=format_type(pokemon["types"]),
        formatted_evolution=" **->** ".join(" **/** ".join(pokedex[name]["locale_name"].upper() for name in names)
                                            for names in pokemon["evolution"]),
        pokemon_go=pokemon_go_info,
        **pokemon
    )

    yield from client.say(message, formatted_message)


@pokedex_.command()
def egg(client: discord.Client, message: discord.Message, egg_type: Annotate.LowerCleanContent):
    """ Get the pokemon hatched from the specified egg_type
    (in distance, e.g. 2 or 5km) """
    # Strip any km suffix (or prefix, whatever)
    egg_type = egg_type.replace("km", "")

    try:
        distance = int(float(egg_type))  # Using float for anyone willing to type 2.0km
    except ValueError:
        yield from client.say(message, "The egg type **{}** is invalid.".format(egg_type))
        return

    pokemon_criteria = []
    egg_types = []

    # Find all pokemon with the specified distance
    for pokemon in sorted(pokedex.values(), key=itemgetter("id")):
        # We've exceeded the generation and no longer need to search
        if pokemon["generation"] not in pokemon_go_gen:
            break

        if "hatches_from" not in pokemon:
            continue

        if pokemon["hatches_from"] not in egg_types:
            egg_types.append(pokemon["hatches_from"])

        if pokemon["hatches_from"] == distance:
            pokemon_criteria.append(pokemon["locale_name"])

    # The list might be empty
    assert pokemon_criteria, "No pokemon hatch from a **{}km** egg. **Valid distances are** ```\n{}```".format(
        distance, ", ".join("{}km".format(s) for s in sorted(egg_types)))

    # Respond with the list of matching criteria
    yield from client.say(message, "**The following Pokémon may hatch from a {}km egg**:```\n{}```".format(
        distance, ", ".join(sorted(pokemon_criteria))))


def assert_type(slot: str):
    """ Assert if a type does not exist, and show the valid types. """
    match = get_close_matches(slot, api["types"], n=1, cutoff=0.4)

    if match:
        matches_string = " Perhaps you meant `{}`?".format(match[0])
    else:
        matches_string = " See `{}help pokedex type`.".format(command_prefix)
    assert slot in api["types"], "**{}** is not a valid pokemon type.{}".format(
        slot.capitalize(), matches_string)


types_str = "**Valid types are** ```\n{}```".format(", ".join(s.capitalize() for s in api["types"]))


def format_efficacy(types: list):
    """ Format an efficacy string so that we can use this function for
    multiple commands. """
    efficacy = ""
    for type_name in types:
        efficacy += \
            "**{0} OFFENSIVE**\n" \
            "Super effective against: `{1}`\n" \
            "Not very effective against: `{2}`\n".format(
                type_name.upper(),
                ", ".join(s.capitalize() for s in sorted(api["types"][type_name]["effective"])) or "None",
                ", ".join(s.capitalize() for s in sorted(api["types"][type_name]["ineffective"])) or "None")

        # Find any type which is effective and ineffective against type_name
        effective, ineffective = [], []
        for other_type_name in api["types"]:
            if type_name in api["types"][other_type_name]["effective"]:
                effective.append(other_type_name)
            elif type_name in api["types"][other_type_name]["ineffective"]:
                ineffective.append(other_type_name)

        efficacy += \
            "**{0} DEFENSIVE**\n" \
            "Not very effective against {1} type: `{2}`\n" \
            "Super effective against {1} type: `{3}`\n".format(
                type_name.upper(),
                type_name,
                ", ".join(s.capitalize() for s in sorted(ineffective)) or "None",
                ", ".join(s.capitalize() for s in sorted(effective)) or "None")
    return efficacy.strip("\n")


@pokedex_.command(name="type", description="Show pokemon with the specified types. {}".format(types_str))
def filter_type(client: discord.Client, message: discord.Message, slot_1: str.lower, slot_2: str.lower=None):
    matched_pokemon = []
    assert_type(slot_1)

    # Find all pokemon with the matched criteria
    if slot_2:
        assert_type(slot_2)

        # If two slots are provided, search for pokemon with both types matching
        for pokemon in pokedex.values():
            if pokemon["types"] == [slot_1, slot_2]:
                matched_pokemon.append(pokemon["locale_name"])
    else:
        # All pokemon have a type in their first slot, so check if these are equal
        for pokemon in pokedex.values():
            if pokemon["types"][0] == slot_1:
                matched_pokemon.append(pokemon["locale_name"])

    types = [slot_1] if slot_2 is None else [slot_1, slot_2]

    # There might not be any pokemon with the specified types
    assert matched_pokemon, "Looks like there are no pokemon of type **{}**!".format(format_type(types))

    yield from client.say(message, "**Pokemon with type {}**: ```\n{}```".format(
        format_type(types), ", ".join(sorted(matched_pokemon))))


@pokedex_.command(aliases="e",
                  description="Display type efficacy (effectiveness) of the specified type. {}".format(types_str))
def effect(client: discord.Client, message: discord.Message, type: str.lower):
    assert_type(type)

    yield from client.say(message, format_efficacy([type]))


@permission("manage_server")
@pokedex_.command(disabled_pm=True, aliases="sf")
def scalefactor(client: discord.Client, message: discord.Message, factor: float=default_scale_factor):
    """ Set the image scaling factor for your server. If no factor is given, the default is set. /
    **This command requires the `Manage Server` permission.**"""
    assert factor <= max_scale_factor, "The factor **{}** is too high **(max={})**.".format(
        factor, max_scale_factor)
    assert min_scale_factor <= factor, "The factor **{}** is too low **(min={})**.".format(
        factor, min_scale_factor)

    if message.server.id not in pokedex_config.data:
        pokedex_config.data[message.server.id] = {}

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
