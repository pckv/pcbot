# PCBOT
WIP discord bot using [discord.py]. 

PCBOT should be supported by all python versions above 3.4.2. It is however only tested and developed in python
3.4.4, so please give me a yell if something is unsupported.

[discord.py]: https://github.com/Rapptz/discord.py

## MongoBot
**For those who have arrived from MongoBot and wish to contribute/have a look/access the resources**, the libraries used are found in `plugins/pokedex.py` and `plugins/pokedexlib/`!

Currently, I only host MongoBot for public use. **If you wish to add the bot to your server, you may use [this link!][mongobot]

[mongobot]: https://discordapp.com/oauth2/authorize?client_id=203868685557956608&scope=bot&permissions=0

## Installing
The bot itself requires no extra python modules, although `prank` plugin needs Pillow. To install the bot, 
one can clone the repo:

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

You should get a prompt asking for your bot token. If you want to login to a regular account, 
use the --email/-e token like so:

```
python bot.py --email EMAIL
```

The bot will prompt for a password the first time you login with an email. For more information, 
see [Command-line arguments][cmd]

[cmd]: https://github.com/PcBoy111/PCBOT/blob/master/README.md#assigning-ownership

## Assigning ownership
After running the bot for the first time, you want to make sure you're assigned the owner account. 
This process is very straight-forward and requires that you have access to the bot log, and can respond
to the bot within 60 seconds of reading the log (By default, the log is printed to the terminal).

**The first step** is to send the command `!setowner` in a private message. The bot will wait for 
a response matching the 3-digit code logged to the console. The logged message looks something like this:

```
CRITICAL [bot] 2016-04-24 23:03:49,138: Owner code for assignment: 263
```

After sending the code in a private message, in this case `263`, your account will be registered as the 
bot owner.

## Command-line arguments
Execute `python bot.py -h` to see a list of supported command-line arguments.

## Plugins
PCBOT has a folder based plugin system. **The documentation for creating these plugins might come along soon**, although if you wish to make one, a good example is found in `pcbot/builtin.py`.

**To remove an unwanted plugin from the bot**, simply remove it from the `plugins/` folder. You are also free to remove any accompanying library folder.

Currently, the owner can reload, unload and load plugins with the `!plugin` command.

When building plugins, make sure you're using syntax supported by your version of python. Considering the bot is
built for version 3.4.2+, the best would be to follow this syntax. 

## Licence
The MIT License (MIT)

Copyright (c) 2016 PC

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
