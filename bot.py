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
from __future__ import annotations

import logging
import asyncio
from math import e
from typing import Any, Final
from collections.abc import Iterable

import discord
from discord import app_commands
from discord.ext import commands

import asyncpg

from store.claimtime import ClaimtimeDBStore

MISSING: Any = discord.utils.MISSING
PREMIUM_SKU_ID: Final[int] = 1256218013930094682
log = logging.getLogger(__name__)

class LegacyBotContext(commands.Context["LegacyBot"]):
    __slots__ = (
        '_cs_premium',
    )

    guild: discord.Guild
    author: discord.Member

    @property
    def reference(self) -> discord.MessageReference | None:
        """:class:`discord.MessageReference`: The context's message reference, or ``None``."""
        return self.message.reference

    @property
    def resolved_reference(self) -> discord.Message | None:
        """:class:`discord.Message`: The resolved reference message, or ``None``."""
        return self.reference and (self.reference.resolved or self.reference.cached_message)  # pyright: ignore[reportReturnType]

    async def buy_premium(self, content: str | None = None, **kwargs: Any) -> discord.Message:
        view = discord.ui.View(timeout=0.1)  # prevent storing it as it does not contain any handable button
        view.add_item(
            discord.ui.Button(
                sku_id=PREMIUM_SKU_ID,
            ),
        )
        kwargs['view'] = view
        return await self.send(content, **kwargs)

    def get_connection(self):
        """:class:`PoolAcquireContext`: A shortcut for :meth:`LegacyBotContext.bot.get_connection <LegacyBot.get_connection>`."""
        return self.bot.get_connection()

    async def is_premium(self) -> bool:
        """:class:`bool`: Returns ``True`` if the current context has the premium SKU bought."""
        if hasattr(self, '_cs_premium'):
            return self._cs_premium

        if self.interaction:
            prem = PREMIUM_SKU_ID in [e.sku_id for e in self.interaction.entitlements]
        else:
            prem = len([_ async for _ in self.bot.entitlements(guild=self.guild, skus=[discord.Object(PREMIUM_SKU_ID)])]) > 0

        self._cs_premium = prem
        return self._cs_premium

def get_guild_prefix(bot: LegacyBot, message: discord.Message) -> list[str]:
    if message.guild is None:
        return ['?']
    prefixes = bot.get_prefixes_for(message.guild.id)
    if prefixes is None:
        bot.schedule_prefix_creation(message.guild.id)
        return ['?']
    return prefixes


class LegacyBot(commands.Bot):
    def __init__(
        self,
        *,
        tree_cls: type[app_commands.CommandTree[LegacyBot]] = app_commands.CommandTree["LegacyBot"],
        description: str | None = None,
        allowed_contexts: app_commands.AppCommandContext = MISSING,
        allowed_installs: app_commands.AppInstallationType = MISSING,
        intents: discord.Intents,
        initial_extensions: Iterable[str],
        **options: Any,
    ) -> None:
        super().__init__(
            get_guild_prefix,
            tree_cls=tree_cls,
            description=description,
            allowed_contexts=allowed_contexts,
            allowed_installs=allowed_installs,
            intents=intents,
            **options,
        )
        self.pool: asyncpg.Pool[asyncpg.Record] = MISSING
        self.initial_extensions: Iterable[str] = initial_extensions

        # here all the guild prefixes will be saved as a
        # {guild_id: [prefix, list]} mapping
        self._guild_prefixes: dict[int, list[str]] = {}
        self._prefix_creation_tasks: set[asyncio.Task] = set()
        self.claimtime_store: ClaimtimeDBStore = ClaimtimeDBStore(self)

    def get_connection(self):
        """:class:`asyncpg.Connection`: Returns a pool connection to the database."""
        return self.pool.acquire()

    def get_prefixes_for(self, guild_id: int, /) -> list[str] | None:
        """Returns the prefixes for a guild.

        Parameters
        ----------
        guild_id: :class:`int`
            The ID of the guild to obtain the prefixes from.

        Returns
        -------
        Optional[List[:class:`str`]]
            The guild prefixes, or ``None`` if not yet loaded.
        """
        return self._guild_prefixes.get(guild_id)

    def schedule_prefix_creation(self, guild_id: int, /) -> None:
        task = asyncio.create_task(self._create_or_cache_guild_config(guild_id), name=f'Create-or-cache-guild-{guild_id}')
        self._prefix_creation_tasks.add(task)
        task.add_done_callback(self._prefix_creation_tasks.remove)

    async def _create_or_cache_guild_config(self, guild_id: int) -> None:
        async with self.get_connection() as conn:
            async with conn.transaction():
                data: asyncpg.Record | None = await conn.fetchrow(
                    'WITH inserted AS '
                    '(INSERT INTO guilds ("id", prefixes) VALUES ($1, $2::varchar[]) ON CONFLICT ("id") DO NOTHING RETURNING prefixes) '
                    'SELECT prefixes FROM inserted UNION ALL SELECT prefixes FROM guilds WHERE "id" = $1 LIMIT 1;',
                    guild_id, ['?'],
                )

                if data is None:
                    # in the strange case where the date was not cached, use this default
                    # so this is not called anymore
                    self._guild_prefixes[guild_id] = ['?']
                else:
                    self._guild_prefixes[guild_id] = data['prefixes']
        # ensure with context manager closure
        return

    async def load_extensions(self, extensions: Iterable[str], /) -> None:
        """Bulk loads extensions.

        Parameters
        ----------
        extensions: Iterable[:class:`str`]
            The extensions to load.
        """

        for ext in extensions:
            await self.load_extension(ext)

    async def load_initial_extensions(self) -> None:
        """Helper method that automatically loads all initial extensions."""
        await self.load_extensions(self.initial_extensions)

    async def load_guild_prefixes(self) -> None:
        async with self.get_connection() as conn:
            data = await conn.fetch(
                'SELECT "id", prefixes::varchar[] FROM guilds;',
            )

        for record in data:
            self._guild_prefixes[int(record['id'])] = record['prefixes']

    async def setup_hook(self) -> None:
        await self.load_guild_prefixes()
        await self.claimtime_store.load()
        await self.load_initial_extensions()

    async def get_context(self, origin: discord.Message | discord.Interaction, *, cls=LegacyBotContext) -> Any:
        return await super().get_context(origin, cls=cls)

    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None:
            return
        await self.process_commands(message)

    async def get_or_fetch_member(self, guild: discord.Guild, id: int, /) -> discord.Member:
        """Gets or fetches a member from ``guild`` with ID ``id``.

        Parameters
        ----------
        guild: :class:`discord.Guild`
            The guild to get or fetch the member from.
        id: :class:`int`
            The ID of the member.
        """

        member = guild.get_member(id)

        if member is None:
            if self.is_ws_ratelimited():
                member = await guild.fetch_member(id)
                guild._add_member(member)  # NOTE: update this if dpy changes it
            else:
                members = await guild.query_members(
                    user_ids=[id],
                    cache=True,
                    limit=1,
                )
                if members:
                    member = members[0]
                else:
                    member = None

        if member is None:
            raise ValueError('member not found')

        return member

    async def get_or_fetch_members(self, guild: discord.Guild, *ids: int) -> list[discord.Member]:
        """Gets, fetches, or queries from the gateway the members from ``guild``.

        Parameters
        ----------
        guild: :class:`discord.Guild`
            The guild to get the members from.
        *ids
            The IDs of the members.
        """

        ret: list[discord.Member] = []
        pending: list[int] = []

        for mid in ids:
            m = guild.get_member(mid)

            if m:
                ret.append(m)
            else:
                pending.append(mid)

        if pending:
            if self.is_ws_ratelimited():
                for pid in pending:
                    m = await guild.fetch_member(pid)
                    ret.append(m)
                    guild._add_member(m)  # NOTE: update this if dpy changes it
            else:
                queried = await guild.query_members(user_ids=pending, cache=True)
                ret.extend(queried)
        return ret

    async def on_guild_join(self, guild: discord.Guild) -> None:
        async with self.get_connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    'INSERT INTO guilds (id) VALUES ($1) ON CONFLICT (id) DO NOTHING;',
                    guild.id,
                )
                await conn.execute(
                    'INSERT INTO claimtimes_config (guild_id) VALUES ($1) ON CONFLICT (id) DO NOTHING;',
                    guild.id
                )
        # ensure context manager closure
        pass

    async def on_ready(self) -> None:
        if not self.user:
            log.warning('Bot received the READY event but does not have a user attached!')
        else:
            log.info(f'Logged in as {self.user}')
