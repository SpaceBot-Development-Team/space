"""
The MIT License (MIT)

Copyright (c) 2025-present Developer Anonymous

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

import traceback

if __name__ == "__main__":
    import asyncio
    import os
    import json
    import sys

    import aiohttp
    import discord
    import asyncpg
    from dotenv import load_dotenv

    from bot import LegacyBot

    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True

    initial = [
        "cogs.giveaways",
        "cogs.meta",
        "cogs.config",
        "cogs.tools",
        "cogs.lyrics_generator",
        "jishaku",
    ]

    DEBUG_MODE: bool = sys.argv[-1] == '--debug'

    load_dotenv()

    def _encode_jsonb(value):
        return json.dumps(value)

    def _decode_jsonb(value):
        return json.loads(value)

    async def init(con):
        await con.set_type_codec(
            'jsonb',
            schema='pg_catalog',
            encoder=_encode_jsonb,
            decoder=_decode_jsonb,
            format='text',
        )

    async def runner():
        tkn = os.environ["BOT_TOKEN"]
        async with LegacyBot(
            initial_extensions=initial,
            intents=intents,
            allowed_mentions=discord.AllowedMentions(
                everyone=False,
                users=True,
                roles=False,
                replied_user=False,
            ),
            debug_webhook_url=os.environ["DEBUG_WEBHOOK_URL"],
        ) as bot:
            async with asyncpg.create_pool(
                # os.environ['DB_URI'].format(os.environ['DB_PASSWORD']),
                user=os.environ["db_user"],
                host=os.environ["db_host"],
                port=int(os.environ["db_port"]),
                password=os.environ["DB_PASSWORD"],
                database=os.environ["db_name"],
                init=init,
                command_timeout=300,
                max_size=20,
                min_size=20,
            ) as pool, aiohttp.ClientSession() as session:
                bot._session = session
                if not DEBUG_MODE:
                    bot.status = discord.Status.idle
                    bot.activity = discord.Game('?help')
                else:
                    bot.command_prefix = '-'
                    bot.NODEBUGREADY = True  # type: ignore

                bot.pool = pool

                discord.utils.setup_logging()

                try:
                    await bot.start(tkn, reconnect=True)
                except Exception as exc:
                    await bot.send_debug_message(
                        embed=discord.Embed(
                            title='Error When Booting Up Bot!',
                            description=f'```py\n{traceback.format_exception(type(exc), exc, exc.__traceback__)[:3996]}```',
                        )
                    )

    asyncio.run(runner())
