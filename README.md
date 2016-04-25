# PCBOT
WIP discord bot using [discord.py]. 

PCBOT should be supported by all python versions above 3.4.2. It is however only tested and developed in python
3.4.4, so please give me a yell if something is unsupported.

[discord.py]: https://github.com/Rapptz/discord.py

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
PCBOT has a folder based plugin system. The plugins do not need any specific imports 
(other than `discord` of course). A template plugin can be found in the `plugins/` folder.

**To remove an unwanted plugin from the bot**, simply remove it from the `plugins/` folder.
*This process of handling plugins will soon be migrated to a blacklist system.*

Currently, the owner can reload, unload and load plugins with the `!plugin` command:

Option | Function
-------|--------
!plugin | list all loaded plugins
!plugin reload [plugin] | reload all or the specified plugin
!plugin unload <plugin> | unload a plugin temporarily
!plugin load <plugin> | load a plugin from the `plugins/` folder

When building plugins, make sure you're using syntax supported by your version of python. Considering the bot is
built for version 3.4.2+, the best would be to follow this syntax. 
