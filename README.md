# PC-BOT-V2
WIP better-than-PCBOT discord bot using [discord.py].
This bot is the successor to PCBOT, my first discord bot. Seemed only fair to give him a second chance.

[discord.py]: https://github.com/Rapptz/discord.py

## Version
PCBOT should be supported by all python versions above 3.4.2. It is however only tested and worked on in python
3.4.4, so please give me a yell if something is unsupported.

## Installing
The bot itself requires no extra python modules, although `prank` plugin needs Pillow. To install the bot, one can clone the repo:

```
git clone https://github.com/PcBoy111/PCBOT.git
```

*Or*, just simply [download the repo as ZIP][zip].

[zip]: https://github.com/PcBoy111/PC-BOT-V2/archive/3.4.zip

## Running
Running the bot is simple. Go to the root directory of the bot, and run bot.py:

```
python bot.py
```

## Command-line arguments
Execute `python bot.py -h` to see a list of supported command-line arguments.

## Plugins
PCBOT has a folder based plugin system. The plugins do not need any specific imports (other than `discord` of course).
A template plugin can be found in the `plugins/` folder as well.

**To remove an unwanted plugin from the bot**, simply remove it from the `plugins/` folder.

When building plugins, make sure you're using syntax supported by your version of python. Considering the bot is
built for version 3.4.2+, the best would be to use this syntax. 
