import json
import pathlib
import random
from datetime import datetime

import discord

from pcbot import Annotate
import plugins
client = plugins.client

words_path = pathlib.Path("plugins/wordlib/")

with open(words_path / "SimpleWordlists" / "Wordlist-Nouns-Common-Audited-Len-3-6.txt") as f:
    nouns = f.read().split("\n")

with open(words_path / "verb.forms.dictionary" / "json" / "verbs-all.json", encoding="ISO-8859-1") as f:
    verbs_json = json.load(f)
    verbs = [verb[0] for verb in verbs_json]

def seed_for_member(member: discord.Member):
    """ Gets the seed for the given member. """
    now = datetime.now()
    return int(member.id) * now.year * now.month * now.day
    

def make_agenda():
    aaa = random.randint(0, 10)   
    if aaa == 0:
        return random.choice(nouns)
    elif aaa == 1:
        return random.choice(verbs)
    else:
        return random.choice(verbs) + " " + random.choice(nouns)


@plugins.command()
async def horoscope(message: discord.Message, member: discord.Member=Annotate.Self):
    """ Shows your horoscope or the horoscope for the given member. """
    random.seed(seed_for_member(member))

    dos = [make_agenda().capitalize() for _ in range(3)]
    donts = [make_agenda().capitalize() for _ in range(3)]

    embed = discord.Embed(color=member.color)
    embed.set_author(name=member.display_name, icon_url=member.avatar_url)
    embed.add_field(name="Do", value="\n".join(dos))
    embed.add_field(name="Don't", value="\n".join(donts))
    
    await client.send_message(message.channel, embed=embed)

