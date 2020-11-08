import json
import pathlib
import random
from datetime import datetime

import pendulum

from pcbot import Annotate
import plugins
client = plugins.client

words_path = pathlib.Path("plugins/wordlib/")

with open(words_path / "SimpleWordlists" / "Wordlist-Nouns-Common-Audited-Len-3-6.txt") as f:
    nouns = f.read().split("\n")

with open(words_path / "SimpleWordlists" / "Wordlist-Nouns-All.txt") as f:
    all_nouns = f.read().split("\n")

with open(words_path / "SimpleWordlists" / "Wordlist-Adjectives-All.txt") as f:
    adjectives = f.read().split("\n")

with open(words_path / "SimpleWordlists" / "Wordlist-Adverbs-All.txt") as f:
    adverbs = f.read().split("\n")

with open(words_path / "verb.forms.dictionary" / "json" / "verbs-all.json", encoding="ISO-8859-1") as f:
    verbs_json = json.load(f)
    verbs = [verb[0] for verb in verbs_json]


def seed_for_member(member: discord.Member):
    """ Gets the seed for the given member. """
    now = datetime.now()
    return int(member.id) * now.year * now.month * now.day
    

def random_noun():
    selected_nouns = all_nouns if random.randint(0, 5) == 0 else nouns

    if random.randint(0, 3) == 0:
        return random.choice(adjectives) + " " + random.choice(selected_nouns)
    
    return random.choice(selected_nouns)


def make_agenda_two():
    agenda = random.choice(verbs)
    if random.randint(0, 8) == 0:
        return random_noun() if random.randint(0, 1) == 0 else agenda

    agenda += " " + random_noun()
    if random.randint(0, 5) > 1:
        return agenda
    
    return agenda + " " + random.choice(adverbs)


@plugins.command()
async def horoscope(message: discord.Message, member: discord.Member=Annotate.Self):
    """ Shows your horoscope or the horoscope for the given member. """
    random.seed(seed_for_member(member))

    dos = ["\u2022 " + make_agenda_two().capitalize() for _ in range(3)]
    donts = ["\u2022 " + make_agenda_two().capitalize() for _ in range(3)]

    embed = discord.Embed(color=member.color, title=datetime.now().strftime("%A"))
    embed.set_author(name=member.display_name, icon_url=member.avatar_url)
    embed.add_field(name="Do", value="\n".join(dos))
    embed.add_field(name="Don't", value="\n".join(donts))
    
    await client.send_message(message.channel, embed=embed)


def make_agenda():
    aaa = random.randint(0, 10)   
    if aaa == 0:
        return random.choice(nouns)
    elif aaa == 1:
        return random.choice(verbs)
    else:
        return random.choice(verbs) + " " + random.choice(nouns)


@horoscope.command()
async def old(message: discord.Message, member: discord.Member=Annotate.Self):
    """ Shows your horoscope or the horoscope for the given member. """
    random.seed(seed_for_member(member))

    dos = [make_agenda().capitalize() for _ in range(3)]
    donts = [make_agenda().capitalize() for _ in range(3)]

    embed = discord.Embed(color=member.color, title=datetime.now().strftime("%A"))
    embed.set_author(name=member.display_name, icon_url=member.avatar_url)
    embed.add_field(name="Do", value="\n".join(dos))
    embed.add_field(name="Don't", value="\n".join(donts))
    
    await client.send_message(message.channel, embed=embed)
