"""
The MIT License (MIT)

Copyright (c) 2024-present Developer Anonymous

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

from __future__ import annotations

import os
import logging

from _types import Bot

import discord
import aiohttp

if '.env' in os.listdir('.'):
    from dotenv import load_dotenv
    load_dotenv()

try:
    TOKEN = os.environ["TOKEN"]
    DB_URL = os.environ["DB_URL"]
    DB_PASSWORD = os.environ["DB_PASSWORD"]
    TGG_TOKEN = os.environ["TGG_TOKEN"]
    JEYY_TOKEN = os.environ["JEYY_TOKEN"]

    for lavalink_key in (
        'LAVALINK_IDENTIFIER',
        'LAVALINK_PASSWORD',
        'LAVALINK_HOST',
        'LAVALINK_PORT',
    ):
        os.environ[lavalink_key]
except KeyError as exc:
    raise RuntimeError(
        "Could not initialize bot because the environment was not set"
    ) from exc

if ".git" not in os.listdir("."):
    INITIALIZE_GIT_HISTORY = [
        "git init",
        "git remote add bot_source https://github.com/SpaceBot-Development-Team/space.git",
        "git branch -M master",
        "git config user.name SpaceBotLauncher",
        "git add .",
        'git commit -m "Never commited changes"',
        "git pull bot_source master",
    ]
    for command in INITIALIZE_GIT_HISTORY:
        os.system(command)

extensions: list[str] = [
    "cogs.admin",
    "cogs.owner",
    "cogs.games",
    "cogs.vouchs",
    "cogs.meta",
    "cogs.user_installable",
    "cogs.suggestions",
    "cogs.warns",
    "cogs.guild_commands.limited_guilds",
]  # 'cogs.music',]
Bot.cog_emojis = {
    "Vouchs": "<:vouch:1241434529491587193>",
    "Meta": "\N{GEAR}",
    "Premium": "<a:ANTARTICO_Fiesta:1204184776119164950>",
    "Musica": "<:ANTARTICO_Fiesta:1179576653614170225>",
    "Juegos": "<a:ANTARTICO_hehe:1204099792788135977>",
    "Admin": "<a:STAFF:1217970870350385212>",
    "Tickets": "\N{TICKET}",
}
bot = Bot(
    models="models",
    db_url=DB_URL,
    db_password=DB_PASSWORD,
    strip_after_prefix=True,
    chunk_guilds_at_startup=False,
    tokens={"top.gg": TGG_TOKEN, "jeyy": JEYY_TOKEN},
    initial_extensions=extensions,
)

os.environ["JISHAKU_NO_DM_TRACEBACK"] = "True"
os.environ["JISHAKU_HIDE"] = "True"


async def create_tables_for(guild: discord.Guild) -> None:
    from models import Guild, SuggestionsConfig, VouchsConfig, WarnsConfig

    tables = (Guild, SuggestionsConfig, VouchsConfig, WarnsConfig)
    for table in tables:
        if not await table.exists(id=guild.id):
            await table.create(id=guild.id)
    bot.logger.info("Ensured all guild related configs for %s", guild.id)


@bot.event
async def on_ready() -> None:
    """Event called when client is ready or resumed a session"""
    bot.logger.info("READY event recieved")


@bot.event
async def on_guild_join(guild: discord.Guild) -> None:
    """Event called when the bot joins a guild"""
    bot.logger.debug("Joined a new guild: %s", guild.id)

    async for entry in guild.audit_logs(limit=2, action=discord.AuditLogAction.bot_add):
        if entry.user is not None:
            await entry.user.send(embed=bot.thanks_for_adding())
    await create_tables_for(guild)


@bot.event
async def on_guild_available(guild: discord.Guild):
    await create_tables_for(guild)


async def runner():
    """Runner method to start the client"""
    async with aiohttp.ClientSession() as session:
        discord.utils.setup_logging(level=logging.INFO)
        bot.set_session(session)

        async with bot:
            await bot.start(TOKEN, reconnect=True)


if __name__ == "__main__":
    import asyncio

    asyncio.run(runner())
