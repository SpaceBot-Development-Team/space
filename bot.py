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

import datetime
import logging
import asyncio
import traceback
from typing import Any, Final
from collections.abc import Iterable

import discord
from discord import app_commands
from discord.ext import commands

import asyncpg

from store.claimtime import ClaimtimeDBStore
from errors import ModuleDisabled

MISSING: Any = discord.utils.MISSING
PREMIUM_SKU_ID: Final[int] = 1256218013930094682
log = logging.getLogger(__name__)

class LegacyBotContext(commands.Context["LegacyBot"]):
    __slots__ = (
        '_cs_premium',
    )

    guild: discord.Guild
    author: discord.Member
    channel: discord.TextChannel | discord.VoiceChannel | discord.StageChannel | discord.ForumChannel

    @property
    def reference(self) -> discord.MessageReference | None:
        """:class:`discord.MessageReference`: The context's message reference, or ``None``."""
        return self.message.reference

    @property
    def resolved_reference(self) -> discord.Message | None:
        """:class:`discord.Message`: The resolved reference message, or ``None``."""
        return self.reference and (self.reference.resolved or self.reference.cached_message)  # pyright: ignore[reportReturnType]

    @property
    def created_at(self) -> datetime.datetime:
        """:class:`datetime.datetime`: The time when this context was created at."""
        if self.interaction:
            return self.interaction.created_at
        return self.message.created_at

    @property
    def not_found_enabled(self) -> bool:
        return False

    async def buy_premium(self, content: str | None = None, **kwargs: Any) -> discord.Message:
        view = discord.ui.View(timeout=0.1)  # prevent storing it as it does not contain any handable button
        view.add_item(
            discord.ui.Button(
                sku_id=PREMIUM_SKU_ID,
            ),
        )
        kwargs['view'] = view
        return await self.send(content, **kwargs)

    async def reply_buy_premium(self, content: str | None = None, **kwargs: Any) -> discord.Message:
        kwargs['reference'] = self.to_reference()
        return await self.buy_premium(content, **kwargs)

    def get_connection(self):
        """:class:`PoolAcquireContext`: A shortcut for :meth:`LegacyBotContext.bot.get_connection <LegacyBot.get_connection>`."""
        return self.bot.get_connection()

    async def is_premium(self) -> bool:
        """:class:`bool`: Returns ``True`` if the current context has the premium SKU bought."""
        if hasattr(self, '_cs_premium'):
            return self._cs_premium

        if self.interaction:
            prem = (
                (PREMIUM_SKU_ID in [e.sku_id for e in self.interaction.entitlements])
                or
                (PREMIUM_SKU_ID in self.interaction.entitlement_sku_ids)
            )
        else:
            prem = len([_ async for _ in self.bot.entitlements(user=self.author, guild=self.guild, skus=[discord.Object(PREMIUM_SKU_ID)])]) > 0

        self._cs_premium = prem
        return self._cs_premium

    def to_reference(
        self,
        *,
        fail_if_not_exists: bool = False,
        type: discord.MessageReferenceType = discord.MessageReferenceType.reply,
    ) -> discord.MessageReference:
        """Creates a :class:`discord.MessageReference` from the current message.

        Parameters
        ----------
        fail_if_not_exists: :class:`bool`
            Whether the referenced message should raise :class:`discord.HTTPException`
            if the message no longer exists or Discord could not fetch the message.
        type: :class:`discord.MessageReferenceType`
            The type of message reference.

        Returns
        ---------
        :class:`discord.MessageReference`
            The reference to this message.
        """
        return self.message.to_reference(
            fail_if_not_exists=fail_if_not_exists,
            type=type,
        )

    @property
    def id(self) -> int:
        """:class:`int`: Returns this context ID."""
        return self.message.id

    def to_message_reference_dict(self):
        return self.message.to_message_reference_dict()


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
        debug_webhook_url: str | None = None,
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
        self._disabled_modules: dict[int, list[str]] = {}
        self.__wh_url: str | None = debug_webhook_url

        self.add_check(self.module_enabled)

    async def module_enabled(self, context: LegacyBotContext) -> bool:
        if not context.command:
            return True
        if not context.cog:
            return True
        if context.cog.qualified_name in self._disabled_modules.get(context.guild.id, []):
            raise ModuleDisabled(context.cog.qualified_name)
        return True

    def get_connection(self):
        """:class:`asyncpg.Connection`: Returns a pool connection to the database."""
        return self.pool.acquire()

    @discord.utils.cached_property
    def debug_webhook(self) -> discord.Webhook | None:
        """Optional[:class:`discord.Webhook`]: Returns the debug webhook, or ``None``"""
        if self.__wh_url is not None:
            return discord.Webhook.from_url(self.__wh_url, client=self)
        return None

    async def send_debug_message(
        self,
        content: str | None = None,
        **kwargs: Any,
    ) -> discord.WebhookMessage | None:
        if self.debug_webhook is None:
            return None
        kwargs['wait'] = True
        return await self.debug_webhook.send(content, **kwargs)

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

    async def load_disabled_modules(self) -> None:
        async with self.get_connection() as conn:
            rows = await conn.fetch(
                'SELECT ("id", disabled_modules::text[]) FROM guilds;',
            )

        for row in rows:
            self._disabled_modules[int(row['id'])] = row['disabled_modules']

    async def update_disabled_modules(self, guild_id: int, disabled_modules: list[str]) -> None:
        async with self.get_connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    'UPDATE guilds SET disabled_modules = $1::text[] WHERE "id" = $2;',
                    disabled_modules, guild_id,
                )

        self._disabled_modules[guild_id] = disabled_modules

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
        await self.load_disabled_modules()
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

        if self.application and self.application.team and self.application.team.owner:
            channel = await self.create_dm(self.application.team.owner)
            await channel.send(
                content=f'New guild joined: {guild.name}',
            )

    async def on_command_error(self, context: LegacyBotContext, error: commands.CommandError) -> None:
        embed = discord.Embed(
            title='An error occurred!',
            colour=discord.Colour.dark_red(),
        )
        send_debug_log = False

        if isinstance(error, commands.CommandOnCooldown):
            reset = context.created_at + datetime.timedelta(seconds=error.retry_after)
            embed.description = f'You are on cooldown! Try again {discord.utils.format_dt(reset, style="R")}'
        elif isinstance(error, commands.MissingRequiredFlag):
            embed.description = f'You missed a required flag "{error.flag.name}": {error.flag.description}'
        elif isinstance(error, commands.TooManyFlags):
            embed.description = f'Too many values provided to "{error.flag.name}"! It takes {error.flag.max_args} values and you provided {len(error.values)}!'
        elif isinstance(error, commands.MissingFlagArgument):
            embed.description = f'You did not provide a value for flag "{error.flag.name}"!'
        elif isinstance(error, commands.BadFlagArgument):
            embed.description = f'"{error.argument}" is not a valid value for flag "{error.flag.name}"!'
        elif isinstance(error, commands.NSFWChannelRequired):
            embed.description = 'This command can only be used on NSFW channels!'
        elif isinstance(error, commands.BotMissingAnyRole):
            fmt = [f'<@&{role}>' if isinstance(role, int) else role for role in error.missing_roles]
            embed.description = f'I need {discord.utils._human_join(fmt)} roles to execute this command!'
        elif isinstance(error, commands.MissingAnyRole):
            fmt = [f'<@&{role}>' if isinstance(role, int) else role for role in error.missing_roles]
            embed.description = f'You need {discord.utils._human_join(fmt)} roles to execute this command!'
        elif isinstance(error, commands.BotMissingRole):
            r = error.missing_role if isinstance(error.missing_role, str) else f'<@&{error.missing_role}>'
            embed.description = f'I need the {r} role to execute this command!'
        elif isinstance(error, commands.MissingRole):
            r = error.missing_role if isinstance(error.missing_role, str) else f'<@&{error.missing_role}>'
            embed.description = f'You need the {r} role to execute this command!'
        elif isinstance(error, commands.BotMissingPermissions):
            fmt = discord.utils._human_join(
                [m.replace('_', ' ').replace('guild', 'server').title()
                 for m in error.missing_permissions
                ],
                final='and',
            )
            embed.description = f'I need {fmt} permissions to execute this command!'
        elif isinstance(error, commands.MissingPermissions):
            fmt = discord.utils._human_join(
                [m.replace('_', ' ').replace('guild', 'server').title()
                 for m in error.missing_permissions
                ],
                final='and',
            )
            embed.description = f'You need {fmt} permissions to execute this command!'
        elif isinstance(error, commands.RangeError):
            fmt = []
            is_string = isinstance(error.value, str)
            if error.maximum is not None:
                if is_string:
                    fmt.append(f'be up to {error.maximum} long')
                else:
                    fmt.append(f'be less than {error.maximum}')
            if error.minimum is not None:
                if is_string:
                    fmt.append(f'be at least {error.minimum} long')
                else:
                    fmt.append(f'be greater than {error.minimum}')
            embed.description = f'The value "{error.value}" must {discord.utils._human_join(fmt, final="and")}'
        elif isinstance(error, commands.BadBoolArgument):
            embed.description = f'"{error.argument}" is not a valid boolean!'
        elif isinstance(error, commands.SoundboardSoundNotFound):
            embed.description = f'Soundboard sound with name or ID "{error.argument}" was not found!'
        elif isinstance(error, commands.ScheduledEventNotFound):
            embed.description = f'Scheduled event with name or ID "{error.argument}" was not found!'
        elif isinstance(error, commands.GuildStickerNotFound):
            embed.description = f'Sticker with name or ID "{error.argument}" was not found!'
        elif isinstance(error, commands.PartialEmojiConversionFailure):
            embed.description = f'"{error.argument}" could not be converted to a valid emoji!'
        elif isinstance(error, commands.EmojiNotFound):
            embed.description = f'Emoji with name or ID "{error.argument}" was not found!'
        elif isinstance(error, commands.BadInviteArgument):
            embed.description = f'Invite "{error.argument}" was not found or was expired!'
        elif isinstance(error, commands.RoleNotFound):
            embed.description = f'Role with name or ID "{error.argument}" was not found!'
        elif isinstance(error, commands.BadColourArgument):
            embed.description = f'Could not convert "{error.argument}" to a valid colour!'
        elif isinstance(error, commands.ThreadNotFound):
            embed.description = f'Thread with name or ID "{error.argument}" was not found!'
        elif isinstance(error, commands.ChannelNotReadable):
            embed.description = f'I do not have Read Messages permissions on {error.argument.mention}, and I need it to execute the command!'
        elif isinstance(error, commands.ChannelNotFound):
            embed.description = f'Channel with name or ID "{error.argument}" was not found!'
        elif isinstance(error, commands.UserNotFound):
            embed.description = f'User with name or ID "{error.argument}" was not found!'
        elif isinstance(error, commands.GuildNotFound):
            embed.description = f'Guild with name or ID "{error.argument}" was not found!'
        elif isinstance(error, commands.MemberNotFound):
            embed.description = f'Member with name or ID "{error.argument}" was not found!'
        elif isinstance(error, commands.MessageNotFound):
            embed.description = f'Message with ID or url "{error.argument}" was not found!'
        elif isinstance(error, commands.NotOwner):
            return  # it is owner only then why even bother to tell them, if it was hidden then we should not provide a response
        elif isinstance(error, commands.MaxConcurrencyReached):
            bucket = error.per.name
            if bucket == 'default':
                embed.description = f'This command can only be used {error.number} times concurrently globally!'
            else:
                embed.description = f'This command can only be used {error.number} times concurrently per {bucket}'
        elif isinstance(error, commands.TooManyArguments):
            embed.description = 'Too many arguments provided to the command!'
        elif isinstance(error, commands.DisabledCommand):
            embed.description = 'This command is disabled!'
        elif isinstance(error, commands.CommandNotFound):
            if context.not_found_enabled:
                embed.description = f'Command "{context.invoked_with}" not found!'
            else:
                return
        elif isinstance(error, commands.NoPrivateMessage):
            embed.description = 'This command can only be used on servers!'
        elif isinstance(error, commands.PrivateMessageOnly):
            embed.description = 'This command can only be used on private messages!'
        elif isinstance(error, commands.BadLiteralArgument):
            embed.description = f'"{error.argument}" is not a valid choice available in {discord.utils._human_join(error.literals)}'
        elif isinstance(error, commands.BadUnionArgument):
            embed.description = f'"{error.param.name}" value was not valid!'
        elif isinstance(error, commands.ExpectedClosingQuoteError):
            embed.description = f'A value\'s quote was not closed, expected `{error.close_quote}`'
        elif isinstance(error, commands.InvalidEndOfQuotedStringError):
            embed.description = f'A space was expected after quote closure on a value, but got `{error.char}` instead'
        elif isinstance(error, commands.UnexpectedQuoteError):
            embed.description = f'Found a quote in a non-quoted value: `{error.quote}`'
        elif isinstance(error, commands.MissingRequiredAttachment):
            embed.description = 'You are missing one attachment to execute this command!'
        elif isinstance(error, commands.MissingRequiredArgument):
            assert context.command
            embed.description = f'`{error.param.name}` is missing! Make sure you follow the command syntax: `{context.command.signature}`'
        elif isinstance(error, ModuleDisabled):
            embed.description = str(error)
        else:
            embed.description = f'An unknown exception has occurred: {error}'
            error = getattr(error, '__original__', error)
            send_debug_log = True

        await context.reply(embed=embed)

        if send_debug_log:
            await self.send_debug_message(
                embed=discord.Embed(
                    title=f'An unknown error occurred on {context.command.name}',
                    description=f'Executed by: {context.author} ({context.author.id})\nExecution date: {discord.utils.format_dt(context.created_at)}',
                    colour=discord.Colour.red(),
                ).add_field(
                    name='Exception traceback:',
                    value=f'{traceback.format_exception(type(error), value=error, tb=error.__traceback__)}',
                ),
            )

    async def on_ready(self) -> None:
        if not self.user:
            log.warning('Bot received the READY event but does not have a user attached!')
        else:
            log.info(f'Logged in as {self.user}')

        if not getattr(self, 'NODEBUGREADY', False):
            await self.send_debug_message(
                embed=discord.Embed(
                    title='\N{INFORMATION SOURCE} Bot ready!',
                    description='You can now set up the git repository using ``jsk sh``',
                    colour=discord.Colour.blue(),
                ),
            )
