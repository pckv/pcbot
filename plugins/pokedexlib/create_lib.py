import json
from collections import defaultdict
from operator import itemgetter

import csv

pokedex = dict(
    pokemon={},
    generations=[],
    types={}
)


def get_pokemon_name(pokemon_id: int):
    """ Return the name of a pokemon's ID. """
    for name, value in pokedex["pokemon"].items():
        if value["id"] == pokemon_id:
            return name

    return None


def get_type_name(type_id: int):
    """ Return the name of a type's ID. """
    for name, value in pokedex["types"].items():
        if value["id"] == type_id:
            return name

    return None


def main():
    print("Initializing...")

    with open("csv/pokemon_species.csv") as f:
        r = csv.DictReader(f)
        for row in r:
            gen = int(row["generation_id"])

            pokedex["pokemon"][row["identifier"]] = dict(
                id=int(row["id"]),
                name=row["identifier"],
                generation=gen,
                evolution_id=int(row["evolution_chain_id"]),
                evolves_from_id=int(row["evolves_from_species_id"] or 0)
            )

            if gen not in pokedex["generations"]:
                pokedex["generations"].append(gen)

    with open("csv/pokemon.csv") as f:
        r = csv.DictReader(f)
        for row in r:
            name = get_pokemon_name(int(row["id"]))
            if name not in pokedex["pokemon"]:
                continue

            pokedex["pokemon"][name].update(dict(
                height=float(row["height"]) / 10,
                weight=float(row["weight"]) / 10
            ))

    # HUGE and confusing way to create our evolutions! Basically, they are all
    # chained and they are all lists.
    evolution = defaultdict(list)
    sorted_for_evo = [
        mon for mon in sorted(pokedex["pokemon"].values(), key=itemgetter("id")) if mon["evolves_from_id"] == 0
    ]
    sorted_for_evo.extend(
        [
            mon for mon in sorted(pokedex["pokemon"].values(), key=itemgetter("id")) if mon["evolves_from_id"] > 0
        ]
    )
    for mon in sorted_for_evo:
        # First pokemon in the chain
        if not evolution[mon["evolution_id"]]:
            evolution[mon["evolution_id"]].append([mon["name"]])
            continue

        evolves_from = get_pokemon_name(mon["evolves_from_id"])

        if evolves_from is None:
            index = 0
        else:
            # Get the index of the list containing said pokemon and add 1
            index = [i for i, v in enumerate(evolution[mon["evolution_id"]]) if evolves_from in v][0] + 1

        if len(evolution[mon["evolution_id"]]) > index:
            evolution[mon["evolution_id"]][index].append(mon["name"])
        else:
            evolution[mon["evolution_id"]].append([mon["name"]])

    for name, mon in pokedex["pokemon"].items():
        mon["evolution"] = evolution[mon["evolution_id"]]

    types = {}
    with open("csv/types.csv") as f:
        r = csv.DictReader(f)
        for row in r:
            types[int(row["id"])] = row["identifier"]

    with open("csv/pokemon_types.csv") as f:
        r = csv.DictReader(f)
        for row in r:
            name = get_pokemon_name(int(row["pokemon_id"]))
            if name not in pokedex["pokemon"]:
                continue

            type_name_ = types[int(row["type_id"])]

            if "types" in pokedex["pokemon"][name]:
                pokedex["pokemon"][name]["types"].append(type_name_)
            else:
                pokedex["pokemon"][name]["types"] = [type_name_]

            if name not in pokedex["types"]:
                pokedex["types"][type_name_] = dict(
                    id=int(row["type_id"]),
                    name=type_name_,
                    damage_factor={}
                )

    with open("csv/pokemon_species_names.csv", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            name = get_pokemon_name(int(row["species_id"]))
            if name not in pokedex["pokemon"]:
                continue

            pokedex["pokemon"][name]["genus"] = row["genus"]
            pokedex["pokemon"][name]["locale_name"] = row["name"]

    with open("csv/pokemon_species_flavor_text.csv", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            name = get_pokemon_name(int(row["species_id"]))
            if name not in pokedex["pokemon"]:
                continue

            pokedex["pokemon"][name]["description"] = row["flavor_text"].replace("\n", " ").replace("\u2019", "'")

    with open("csv/pokemon_go.csv") as f:
        r = csv.DictReader(f)
        for row in r:
            name = get_pokemon_name(int(row["id"]))
            if name not in pokedex["pokemon"]:
                continue

            if row["evolution_cost"]:
                pokedex["pokemon"][name]["evolution_cost"] = int(row["evolution_cost"])

            if row["hatches_from"]:
                pokedex["pokemon"][name]["hatches_from"] = int(row["hatches_from"])

    # Add missingno (id 0)
    pokedex["pokemon"]["missingno"] = dict(
        id=0,
        name="missingno",
        locale_name="missingno.",
        weight=1590.5,
        height=3.0,
        evolution=[["missingno"]],
        evolves_from_id=0,
        evolution_id=0,
        genus="???",
        types=["normal", "999"],
        description="Ç̻̼͚͔̤̎ͧ̅̈́o̧̫̫̖̠͉̹ͤ͗m͂͐̾͐͢͠ͅm̶̲̬̰̦̘͍̄̃̌͗͊͋͡ę̬̜̩̙̍͊̉ṇ̨̡̻̪̰̏̉͢t͂̓̑ͩ͋ͮ"
                    "̯̪̉̂͊s̳̭͓͇̤͛ͧ̀́͋͑͛ͨ̋ ̷͓̱̝͔ͥ͑͝d̤͖̫͙̝͙̱̍̓̑̃ͪ̇́͜u̸͎͚͇̲̮̳̰͎ͬ͌̑͒ͣ͋ͯͦͥ͘r͐͊͐̆"
                    "̭̲̳͍̲̏ͫͩ̐i̶̳͕͕̹̟̠͙̞͗ͤ̍̍n̮̙̼̬̦̫̞̟̣ͤ̏̑ͬ̏̋̉̄̕͟ğ̡͇̼͇͔̼̙̞͂͗̍͆̾ͦ ̨̧̭͎̺͖̰̬̦̬ͧ̽́̈̐ͫ̽ͭͭ͟c̈́"
                    "̛̼̾̍̍̐̃́r̠͉͇ͦ̀ͨ̀͂͟ͅe̡̡̻̞͇͎̠̘ͤ̐͑̋̆ͪͮ̋̃ạ̵͙̤̲̪̩͇̋̄̋ͤͥ̽̕͟t̴ͨ͒ͮ͛͑ͦ̀"
                    "̖̪̼͙͇̖̼͕ǐ̴̧͚̂ͫͬ̆̓͂ǫ̸̜̺̎̃̀ṇ͈̦́̃͟.̟̼̠̭̩ͫͭ̒̃͆̐͑͞",
        generation=1
    )

    # Add type efficacy information (super effective/not very effective)
    with open("csv/type_efficacy.csv") as f:
        r = csv.DictReader(f)
        for row in r:
            name = get_type_name(int(row["damage_type_id"]))
            name_target = get_type_name(int(row["target_type_id"]))
            damage = int(row["damage_factor"]) / 100

            pokedex["types"][name]["damage_factor"][name_target] = damage

            # if damage == 200:
            #     pokedex["types"][name]["effective"].append(name_target)
            # elif damage == 50:
            #     pokedex["types"][name]["ineffective"].append(name_target)

    # SAVE JSON
    with open("pokedex.json", "w") as f:
        json.dump(pokedex, f, sort_keys=True, indent=4)

    print("Library created.")

if __name__ == "__main__":
    main()
