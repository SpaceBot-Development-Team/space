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

import asyncio
import datetime
import logging
import random
import re
from typing import Annotated, TYPE_CHECKING

import asyncpg
import discord
from discord.ext import commands, tasks

from errors import BadDuration, BadWinnersArgument, NoGiveawayPrivileges
from store.claimtime import ClaimtimeDBStore

if TYPE_CHECKING:
    from typing import TypedDict

    from bot import LegacyBot, LegacyBotContext as Context

    from discord.types.embed import Embed as EmbedPayload

    class EmbedVariablesData(TypedDict):
        prize: str
        host: discord.abc.User
        winner_amount: int
        ends_at: datetime.datetime
        guild: discord.Guild
        winner_list: list[int] | None

    class WinMessageVariablesData(TypedDict):
        claimtime: float
        prize: str
        host: discord.abc.User
        winner: discord.Member

DURATION_REGEX = re.compile(r'(\d{1,5}(?:[.,]?\d{1,5})?)([smhd])')
log = logging.getLogger(__name__)

class WinnersConverter(commands.Converter[int]):
    __slots__ = ()

    async def convert(self, ctx: Context, argument: str) -> int:
        if argument.endswith('w'):
            argument = argument.removesuffix('w')
        if not argument.isdigit():
            raise BadWinnersArgument()
        return int(argument)


Winners = Annotated[int, WinnersConverter]


class Duration(commands.Converter["Duration"]):
    """Represents a giveaway duration.

    Attributes
    ----------
    relative: :class:`float`
        The relative offset that the argument provided.
    resolved: :class:`datetime.datetime`
        The resolved datetime, essentialy: now() + timedelta(miliseconds=relative)
    """

    __slots__ = (
        'relative_float',
        'relative_delta',
        'resolved',
    )

    CONVERT_MAP = {'d': 86400,'h': 3600, 'm': 60, 's': 1}

    if TYPE_CHECKING:
        relative_float: float
        relative_delta: datetime.timedelta
        resolved: datetime.datetime

    async def convert(self, ctx: Context, argument: str) -> Duration:
        matches = DURATION_REGEX.findall(argument.lower())
        if not matches or len(matches) > 1:
            raise BadDuration()

        time, fmt = matches[0]

        try:
            value = self.CONVERT_MAP[fmt] * float(time)
        except KeyError:
            raise BadDuration()
        except ValueError:
            raise BadDuration()
        else:
            self.relative_float = value
            self.relative_delta = datetime.timedelta(seconds=value)
            self.resolved = datetime.datetime.now(datetime.timezone.utc) + self.relative_delta
            return self


def replace_vars(string: str, data: EmbedVariablesData, /) -> str:
    ends = 'Ends' if data['ends_at'] < datetime.datetime.now(datetime.timezone.utc) else 'Ended'
    winner_list = ', '.join([f'<@{user}>' for user in data['winner_list']]) if data['winner_list'] else None
    host = data['host']
    ends_at = data['ends_at']
    return string.replace(
        '{prize}', data['prize'],
    ).replace(
        '{host(username)}', host.name,
    ).replace(
        '{host(mention)}', host.mention,
    ).replace(
        '{time_left}', discord.utils.format_dt(ends_at, 'R'),
    ).replace(
        '{end_time}', discord.utils.format_dt(ends_at, 'F'),
    ).replace(
        '{num_winners}', str(data['winner_amount']),
    ).replace(
        '{ends}', ends,
    ).replace(
        '{server_name}', data['guild'].name,
    ).replace(
        '{winner_list}', winner_list or 'Not decided',
    ).replace(
        '{winners}', winner_list if winner_list is not None else str(data['winner_amount']),
    )


def replace_win_message_vars(string: str, data: WinMessageVariablesData, /) -> str:
    host = data["host"]
    winner = data["winner"]
    created_at = winner.created_at
    joined_at = winner.joined_at or datetime.datetime.now(datetime.timezone.utc)
    return string.replace(
        '{claim_time}', f'{data["claimtime"]} seconds',
    ).replace(
        '{host(username)}', host.name,
    ).replace(
        '{host(mention)}', host.mention,
    ).replace(
        '{winner(username)}', winner.name,
    ).replace(
        '{winner(mention)}', winner.mention,
    ).replace(
        '{winner(created_ago)}', discord.utils.format_dt(created_at, 'R'),
    ).replace(
        '{winner(created_date)}', discord.utils.format_dt(created_at, 'f'),
    ).replace(
        '{winner(joined_ago)}', discord.utils.format_dt(joined_at, 'R'),
    ).replace(
        '{winner(joined_date)}', discord.utils.format_dt(joined_at, 'f'),
    ).replace(
        '{prize}', data["prize"],
    )


def replace_url(url: str, data: EmbedVariablesData, /) -> str:
    guild = data['guild']
    if url == 'server://icon':
        return guild.icon.url if guild.icon else ''
    elif url == 'host://avatar':
        return data['host'].display_avatar.url
    return url


def can_handle_giveaways():
    async def check(ctx: Context) -> bool:
        if ctx.author.guild_permissions.manage_guild:
            return True
        role = discord.utils.get(ctx.author.roles, name='Giveaways')

        if role:
            return True
        raise NoGiveawayPrivileges()

    return commands.check(check)


class LeaveGiveaway(discord.ui.DynamicItem[discord.ui.Button], template=r'leave_giveaway:(?P<message>\d+)'):
    def __init__(self, message_id: int, /) -> None:
        self.message_id: int = message_id
        super().__init__(
            discord.ui.Button(
                style=discord.ButtonStyle.red,
                label='Leave Giveaway',
                custom_id=f'leave_giveaway:{message_id}',
            ),
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction[LegacyBot],
        item: discord.ui.Item[discord.ui.View],
        match: re.Match[str],
        /,
    ) -> 'LeaveGiveaway':
        message_id = match.group('message')
        return cls(int(message_id))

    async def callback(self, interaction: discord.Interaction[LegacyBot]) -> None:
        await interaction.response.defer()
        async with interaction.client.get_connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    'DELETE FROM giveaway_participants WHERE message_id=$1 AND user_id=$2;',
                    self.message_id, interaction.user.id,
                )
        await interaction.edit_original_response(
            content='You have left the giveaway!',
            view=None,
        )


class JoinGiveaway(discord.ui.DynamicItem[discord.ui.Button], template=r'join_giveaway'):
    def __init__(self) -> None:
        super().__init__(
            discord.ui.Button(
                style=discord.ButtonStyle.blurple,
                emoji='\N{PARTY POPPER}',
                custom_id='join_giveaway',
            ),
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction[LegacyBot],
        item: discord.ui.Item[discord.ui.View],
        match: re.Match,
        /,
    ) -> 'JoinGiveaway':
        return cls()

    async def callback(self, interaction: discord.Interaction[LegacyBot]) -> None:
        if interaction.message is None or interaction.message.guild is None:
            await interaction.response.send_message(
                'An error occurred while trying to execute this action! This is most likely an error on Discord side!',
                ephemeral=True,
            )
            return

        cog: Giveaways | None = interaction.client.get_cog('Giveaways')  # pyright: ignore[reportAssignmentType]

        if cog is None:
            await interaction.response.send_message(
                'Giveaways are not currently available, try again later!',
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=True)

        participants = await cog.get_giveaway_participants(interaction.message)

        if interaction.user.id in participants:
            await interaction.followup.send(
                'You are already in this giveaway! Would you like to leave it?',
                view=discord.ui.View(timeout=None).add_item(LeaveGiveaway(interaction.message.id)),
                ephemeral=True,
            )
            return

        try:
            async with interaction.client.get_connection() as conn:
                async with conn.transaction():
                    await conn.execute(
                        'INSERT INTO giveaway_participants (guild_id, channel_id, message_id, user_id) VALUES '
                        '($1, $2, $3, $4)',
                        interaction.message.id, interaction.message.channel.id, interaction.message.id, interaction.user.id,
                    )
        except asyncpg.UniqueViolationError:
            await interaction.followup.send(
                "You are already in this giveaway! Would you like to leave it?",
                view=discord.ui.View(timeout=None).add_item(
                    LeaveGiveaway(
                        interaction.message.id,
                    )
                ),
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                'You have joined this giveaway successfully!',
                ephemeral=True,
            )

PartialMessage = Annotated[discord.PartialMessage | None, commands.PartialMessageConverter]


class Giveaways(commands.Cog):
    """Commands to manage giveaways."""

    __slots__ = ('bot',)

    display_emoji = '\N{PARTY POPPER}'

    DEFAULT_EMBED: EmbedPayload = {
        "title": "{prize}",
        "description": "· {ends} {time_left}\n· Winners: {winners}\n· Hosted by {host(mention)}",
    }

    def __init__(self, bot: LegacyBot) -> None:
        self.bot: LegacyBot = bot

        self.claimtimes: ClaimtimeDBStore = bot.claimtime_store
        self._gw_tasks: dict[int, asyncio.Task[None]] = {}
        self._claimtime_tasks: set[asyncio.Task[None]] = set()

    def cog_load(self) -> None:
        self.end_giveaways.start()
        self.bot.add_dynamic_items(JoinGiveaway, LeaveGiveaway)

    def cog_unload(self) -> None:
        if self.end_giveaways.is_running():
            # we are using stop instead of cancel so the current iteration
            # of the task can be finished, and all the pending giveaways are
            # finished.
            self.end_giveaways.stop()

        self.bot.remove_dynamic_items(JoinGiveaway, LeaveGiveaway)

    async def get_giveaway_participants(self, message: discord.PartialMessage, /) -> list[int]:
        if message.guild is None:
            log.debug('Get Giveaway Participants will return an empty list because guild is None')
            return []
        rows = await self.bot.pool.fetch(
            'SELECT * FROM giveaway_participants WHERE message_id=$1;',
            message.id,
        )
        log.debug('Get Giveaway Participants got rows %s', rows)
        return [r['user_id'] for r in rows]

    async def can_create_giveaways_in(self, ctx: Context) -> bool:
        """:class:`bool`: Returns whether a guild-channel is able to hold any more giveaways."""
        async with ctx.get_connection() as conn:
            data = await conn.fetch(
                'SELECT guild_id, channel_id FROM giveaways WHERE guild_id = $1;',
                ctx.guild.id,
            )

            if await ctx.is_premium():
                if len(data) >= 50:
                    return False
                if len([_ for _ in data if _['channel_id'] == ctx.channel.id]) >= 15:
                    return False
            else:
                if len(data) >= 15:
                    return False
                if len([_ for _ in data if _['channel_id'] == ctx.channel.id]) >= 5:
                    return False
        return True

    async def get_guild_giveaway_embed(self, guild: discord.abc.Snowflake, /) -> EmbedPayload:
        """Fetches a guild's giveaway embed.

        If the guild is not premium, then this will return the default embed.

        Parameters
        ----------
        guild: :class:`discord.abc.Snowflake`
            The guild to obtain the embed from.

        Returns
        -------
        :class:`discord.Embed`
            The embed.
        """

        async with self.bot.get_connection() as conn:
            data: asyncpg.Record | None = await conn.fetchrow(
                'SELECT embed FROM gwconfig WHERE guild_id = $1;',
                guild.id,
            )

        if data is None:
            return self.DEFAULT_EMBED
        return data['embed'] or self.DEFAULT_EMBED

    def format_embed_variables(self, embed: EmbedPayload, data: EmbedVariablesData, /) -> EmbedPayload:
        new: EmbedPayload = {}

        for key, value in embed.items():
            if key in ('title', 'description'):
                if isinstance(value, str) and value:
                    new[key] = replace_vars(value, data)
            elif key == 'url':
                if isinstance(value, str) and value:
                    new[key] = replace_url(value, data)
            elif key == 'footer':
                if isinstance(value, dict) and value:
                    new[key] = {
                        'text': replace_vars(value['text'], data),
                    }
                    
                    icon_url = value.get('icon_url')
                    if icon_url:
                        new[key]['icon_url'] = replace_url(icon_url, data)  # type: ignore
            elif key in ('image', 'thumbnail'):
                if isinstance(value, dict) and value:
                    url = value.pop('url')
                    new[key] = {  # type: ignore
                        'url': replace_url(url, data),
                        **value,
                    }
            elif key == 'fields':
                if isinstance(value, list) and value:
                    fields = []
                    for field in value:
                        fields.append(
                            {
                                'name': replace_vars(field['name'], data),
                                'value': replace_vars(field['value'], data),
                                'inline': field.get('inline', True),
                            },
                        )
                    new['fields'] = fields
            elif key == 'author':
                if isinstance(value, dict) and value:
                    name = value.pop('name')
                    url = value.pop('url')
                    icon_url = value.pop('icon_url')
                    pd = {
                        'name': replace_vars(name, data),
                        **value,
                    }
                    if url:
                        pd['url'] = replace_url(url, data)
                    if icon_url:
                        pd['icon_url'] = replace_url(icon_url, data)

                    new[key] = pd  # type: ignore
            else:
                new[key] = value
        return new

    @commands.hybrid_command()
    @can_handle_giveaways()
    async def gstart(self, ctx: Context, duration: Duration, winners: Winners | None = 1, *, prize: str) -> None:
        """Creates a new giveaway.

        Parameters
        ----------
        duration:
            The duration of the giveaway. 1s/1m/1h/1d.
        winners:
            The amount of winners of the giveaway.
        prize:
            The prize of the giveaway.
        """

        if winners is None:
            winners = 1

        if winners <= 0:
            await ctx.reply('Winner amount must be greater than 0!', ephemeral=True)
            return

        async with ctx.typing():
            if not await self.can_create_giveaways_in(ctx):
                await ctx.buy_premium(
                    'You can only create 5 giveaways per channel up to 15 per server with the Free Plan, upgrade to premium '
                    'to be able to create up to 15 giveaways per channel and 50 per server!',
                )
                return

            if duration.relative_delta.days > 30 and not await ctx.is_premium():
                await ctx.buy_premium(
                    'You can only create giveaways up to 30 days long with the Free Plan, upgrade to premium '
                    'to be able to create giveaways up to 3 months!',
                )
                return

            if winners > 15 and not await ctx.is_premium():
                await ctx.buy_premium(
                    'You can only create giveaways with up to 15 winners with the Free Plan, upgrade to premium '
                    'to be able to create giveaways up to 50 winners!',
                )
                return

            if await ctx.is_premium():
                embed = await self.get_guild_giveaway_embed(ctx.guild)
            else:
                embed = self.DEFAULT_EMBED
            embed = self.format_embed_variables(
                embed,
                {
                    'prize': prize,
                    'host': ctx.author,
                    'ends_at': duration.resolved,
                    'guild': ctx.guild,
                    'winner_amount': winners,
                    'winner_list': None,
                }
            )

            view = discord.ui.View(timeout=None)
            view.add_item(JoinGiveaway())
            msg = await ctx.channel.send(content=':tada: **GIVEAWAY!** :tada:', embed=discord.Embed.from_dict(embed), view=view)

            async with ctx.get_connection() as conn:
                async with conn.transaction():
                    await conn.execute(
                        'INSERT INTO giveaways (guild_id, channel_id, message_id, winner_amount, ends_at, prize, host_id) '
                        'VALUES ($1, $2, $3, $4, $5, $6, $7)',
                        ctx.guild.id, ctx.channel.id, msg.id, winners, duration.resolved, prize, ctx.author.id,
                    )

        if ctx.interaction:
            await ctx.interaction.response.send_message(
                'Giveaway created successfully!',
                ephemeral=True,
            )
        else:
            await ctx.message.delete()

    @commands.hybrid_command(name="greroll")
    @can_handle_giveaways()
    async def greroll(self, ctx: Context, *, giveaway: PartialMessage = None) -> None:
        """Rerolls a giveaway and chooses a new winner.

        This only works for giveaways that are not over 15 days old.

        Parameters
        ----------
        giveaway:
            The giveaway to end.
        """
        if ctx.interaction:
            await ctx.interaction.response.defer(thinking=True, ephemeral=True)

        if giveaway is not None:
            record = await self.get_giveaway(giveaway.id)
        else:
            if ctx.reference and ctx.reference.message_id:
                record = await self.get_giveaway(ctx.reference.message_id)
            else:
                record = await self.get_latest_giveaway(ctx.channel)  # pyright: ignore[reportArgumentType]

        if record is None:
            await ctx.reply('Could not find any giveaways in this channel!', ephemeral=True)
            return

        channel = (giveaway and giveaway.channel) or ctx.channel

        if not isinstance(channel, discord.abc.GuildChannel):
            await ctx.reply('Non-valid giveaway message channel provided!')
            return

        gw_message = channel.get_partial_message(record["message_id"])
        participants = await self.get_giveaway_participants(gw_message)

        if not participants:
            await ctx.reply('Not enough entries to choose a winner!', ephemeral=True)
            return

        winner_id = random.choice(participants)

        await ctx.reply(f'Congrats <@{winner_id}>! You have won **{record["prize"]}**!')

        try:
            ret = await self.bot.get_or_fetch_members(ctx.guild, winner_id, record['host_id'])
        except (ValueError, discord.NotFound):
            await ctx.reply('Could not resolve the winner into a member. This is most likely an error on Discord side.', ephemeral=True)
            return

        if len(ret) < 2:
            await ctx.reply('Could not fetch the giveaway data, try again later!', ephemeral=True)
            return

        winner, host = ret

        claimtime = self.claimtimes.get_member_claimtime(winner)
        if claimtime is None:
            return

        win_message = self.claimtimes.get_win_message(ctx.guild.id)
        if win_message is None:
            return

        data: WinMessageVariablesData = {
            'claimtime': claimtime,
            'host': host,
            'winner': winner,
            'prize': record['prize'],
        }

        if ctx.interaction:
            await ctx.interaction.followup.send('Successfully rerolled the giveaway!', ephemeral=True)
        await self.send_and_end_claimtime(claimtime, data, gw_message, win_message)

    @commands.hybrid_command(name="gend")
    @can_handle_giveaways()
    async def gend(self, ctx: Context, *, giveaway: PartialMessage = None) -> None:
        """Ends a giveaway and chooses all the required winners.

        Parameters
        ----------
        giveaway:
            The giveaway to end.
        """

        if ctx.interaction:
            await ctx.interaction.response.defer(thinking=True, ephemeral=True)

        if giveaway is not None:
            record = await self.get_giveaway(giveaway.id)
        else:
            if ctx.reference and ctx.reference.message_id:
                record = await self.get_giveaway(ctx.reference.message_id)
            else:
                record = await self.get_latest_giveaway(ctx.channel)  # pyright: ignore[reportArgumentType]

        if record is None:
            await ctx.reply(
                "Could not find any giveaways in this channel!", ephemeral=True
            )
            return

        await self.end_giveaway(record, wait=False)

        if ctx.interaction:
            await ctx.interaction.followup.send(
                'Successfully ended the giveaway!',
                ephemeral=True,
            )

    async def get_giveaway(self, message_id: int, /) -> asyncpg.Record | None:
        gw = await self.bot.pool.fetchrow(
            'SELECT * FROM giveaways WHERE message_id=$1;',
            message_id,
        )
        return gw

    async def get_latest_giveaway(self, channel: discord.abc.GuildChannel) -> asyncpg.Record | None:
        guild = channel.guild.id
        chid = channel.id

        gw = await self.bot.pool.fetchrow(
            'SELECT * FROM giveaways WHERE guild_id=$1 AND channel_id=$2 AND ends_at < $3 ORDER BY ends_at LIMIT 1;',
            guild, chid, datetime.datetime.now(datetime.timezone.utc),
        )

        if gw is None:
            return None
        return gw

    async def end_giveaway(self, record: asyncpg.Record, *, wait: bool = True) -> None:
        ends_at = record['ends_at']
        if wait:
            await discord.utils.sleep_until(ends_at)

        guild_id = record['guild_id']
        guild = self.bot.get_guild(guild_id)
        host_id = record['host_id']
        host = (
            (guild and guild.get_member(host_id)) or
            self.bot.get_user(host_id) or
            (await self.bot.fetch_user(host_id))
        )
        prize = record["prize"]

        channel = self.bot.get_partial_messageable(
            record['channel_id'],
            guild_id=guild_id,
        )
        message = channel.get_partial_message(record['message_id'])

        participants = await self.get_giveaway_participants(message)
        winner_amount = record['winner_amount']

        if len(participants) >= winner_amount:
            winner_list = random.choices(participants, k=winner_amount)

            if not guild:
                return

            vars: EmbedVariablesData = {
                'guild': guild,
                'ends_at': record['ends_at'],
                'host': host,
                'prize': prize,
                'winner_amount': winner_amount,
                'winner_list': winner_list,
            }

            embed = await self.get_guild_giveaway_embed(guild)
            embed = self.format_embed_variables(embed, vars)

            message = await message.edit(
                content=':tada: **GIVEAWAY ENDED!** :tada:',
                embed=discord.Embed.from_dict(embed),
                view=None,
            )

            for winner in winner_list:
                await message.reply(
                    f'Congrats <@{winner}>! You have won **{record["prize"]}**!'
                )

            win_message = self.claimtimes.get_win_message(guild.id)

            if win_message is not None:
                resolved_winners = await self.bot.get_or_fetch_members(guild, *winner_list)

                for winner in resolved_winners:
                    claimtime = self.claimtimes.get_member_claimtime(winner)
                    if claimtime is None:
                        continue
                    data: WinMessageVariablesData = {
                        'claimtime': claimtime,
                        'host': host,
                        'winner': winner,
                        'prize': prize,
                    }
                    task = asyncio.create_task(
                        self.send_and_end_claimtime(claimtime, data, message, win_message)
                    )
                    self._claimtime_tasks.add(task)
                    task.add_done_callback(self._claimtime_tasks.remove)

        else:
            await message.reply(f'Could not determine a winner! Needed {winner_amount}, got {len(participants)}.')
            winner_list = []

        async with self.bot.get_connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    'UPDATE giveaways SET ended=$1, winner_list=$2::bigint[] WHERE message_id=$3;',
                    True, winner_list, message.id,
                )

    async def send_and_end_claimtime(self, time: float, data: WinMessageVariablesData, message: discord.PartialMessage, win_message: str) -> None:
        ret = await message.reply(
            replace_win_message_vars(win_message, data)
        )
        await asyncio.sleep(time)
        await ret.reply(f'{time:.2f} seconds finished!')

    def _remove_dead_keys(self) -> None:
        for message_id, task in self._gw_tasks.copy().items():
            if task.done():
                del self._gw_tasks[message_id]

    @tasks.loop(minutes=10)
    async def kill_old_giveaways(self) -> None:
        async with self.bot.get_connection() as conn:
            async with conn.transaction():
                gws = await self.bot.pool.fetch(
                    "DELETE FROM giveaways WHERE ended = True AND now() - ends_at > interval '15 days' RETURNING *;"
                )

                for gw in gws:
                    await conn.execute(
                        'DELETE FROM giveaway_participants WHERE guild_id=$1 AND channel_id=$2 AND message_id=$3;',
                        gw['guild_id'], gw['channel_id'], gw['message_id'],
                    )

    @tasks.loop(seconds=5)
    async def end_giveaways(self) -> None:
        # special thanks to Zapdxs, the original Apollo developer, for sharing this
        # way of finishing future giveaways.

        self._remove_dead_keys()
        fut5 = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=5)
        next_gws: list[asyncpg.Record] = await self.bot.pool.fetch(
            'SELECT * FROM giveaways WHERE NOT ended AND ends_at < $1;', fut5
        )

        for row in next_gws:
            message_id = row['message_id']
            if message_id not in self._gw_tasks:
                self._gw_tasks[message_id] = self.bot.loop.create_task(
                    self.end_giveaway(row),
                    name=f'End-Giveaway-{message_id}',
                )

    @commands.Cog.listener()
    async def on_raw_member_remove(self, payload: discord.RawMemberRemoveEvent) -> None:
        guild_id = payload.guild_id
        user_id = payload.user.id

        async with self.bot.get_connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    'DELETE FROM giveaway_participants WHERE guild_id=$1 AND user_id=$2;',
                    guild_id, user_id,
                )

async def setup(bot: LegacyBot) -> None:
    await bot.add_cog(Giveaways(bot))

async def teardown(bot: LegacyBot) -> None:
    await bot.remove_cog(Giveaways.__cog_name__)
