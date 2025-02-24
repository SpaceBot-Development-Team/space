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
import re
from typing import TYPE_CHECKING, Any

import asyncpg
import discord
from discord.ext import commands

if TYPE_CHECKING:
    from bot import LegacyBot, LegacyBotContext as Context

DURATION_REGEX = re.compile(r'(\d{1,5}(?:[.,]?\d{1,5})?)([smhd])')


class AddPrefixModal(discord.ui.Modal, title='Add A Prefix'):
    prefix = discord.ui.TextInput(
        label='Prefix',
        style=discord.TextStyle.short,
        max_length=15,
        min_length=1,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction[LegacyBot]) -> None:
        await interaction.response.defer()
        self.interaction = interaction
        self.stop()


class ConfigView(discord.ui.View):
    __slots__ = (
        'record',
        'premium',
        'author',
        'message',
    )

    def __init__(self, record: asyncpg.Record, *, premium: bool, author: discord.abc.Snowflake) -> None:
        self.record: dict[str, Any] = dict(record)
        self.author: discord.abc.Snowflake = author
        self.message: discord.Message | None = None

        if 'prefixes' not in self.record:
            prefixes = self.record['prefixes'] = ['?']
        else:
            prefixes = self.record.get('prefixes')
            if prefixes is None:
                prefixes = self.record['prefixes'] = ['?']

        self.premium: bool = premium
        super().__init__(timeout=60*15)  # 15mins

        if len(prefixes) >= 3 and not premium:
            self.add_prefix.disabled = True
        elif len(prefixes) >= 5 and premium:
            self.add_prefix.disabled = True

    async def interaction_check(self, interaction: discord.Interaction[LegacyBot]) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                'You cannot control this panel!',
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self) -> None:
        if self.message:
            await self.message.edit(view=None)

    def get_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title='Server Config',
            colour=discord.Colour.blurple(),
        )
        embed.add_field(
            name='Prefixes:',
            value=', '.join(f'`{pre}`' for pre in self.record['prefixes']),
        )
        return embed

    @discord.ui.button(
        label='Add Prefix',
        style=discord.ButtonStyle.blurple,
    )
    async def add_prefix(self, interaction: discord.Interaction[LegacyBot], button: discord.ui.Button[ConfigView]) -> None:
        prs = self.record["prefixes"]
        if len(prs) >= 3 and not self.premium:
            await interaction.response.send_message(
                'You have reached the limit of 3 prefixes on the Free Plan!',
                ephemeral=True,
            )
            return
        elif len(prs) >= 5 and self.premium:
            await interaction.response.send_message(
                'You have reached the limit of 5 prefixes on the Premium Plan!',
                ephemeral=True,
            )
            return

        modal = AddPrefixModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        prefix = modal.prefix.value

        if prefix is None:
            await modal.interaction.followup.send(
                'Non-valid prefix provided!',
                ephemeral=True,
            )
            return

        self.record["prefixes"].append(prefix)
        if len(prs) + 1 >= 3 and not self.premium:
            button.disabled = True
        elif len(prs) + 1 >= 5 and self.premium:
            button.disabled = True
        await interaction.edit_original_response(embed=self.get_embed(), view=self)

    @discord.ui.button(
        label='Remove Last Prefix',
        style=discord.ButtonStyle.red,
    )
    async def pop_prefix(self, interaction: discord.Interaction[LegacyBot], button: discord.ui.Button[ConfigView]) -> None:
        self.record["prefixes"].pop()
        self.add_prefix.disabled = False
        await interaction.response.edit_message(
            embed=self.get_embed(),
            view=self,
        )

    @discord.ui.button(
        label='Reset',
        style=discord.ButtonStyle.grey,
    )
    async def reset_prefix(self, interaction: discord.Interaction[LegacyBot], button: discord.ui.Button[ConfigView]) -> None:
        self.record["prefixes"] = ['?']
        self.add_prefix.disabled = False
        await interaction.response.edit_message(
            embed=self.get_embed(),
            view=self,
        )

    @discord.ui.button(
        label='Save',
        row=1,
        style=discord.ButtonStyle.green,
    )
    async def save_config(self, interaction: discord.Interaction[LegacyBot], button: discord.ui.Button[ConfigView]) -> None:
        if len(self.record["prefixes"]) == 0:
            await interaction.response.send_message(
                'You need at least 1 prefix to save this configuration!',
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=True)
        async with interaction.client.get_connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    'UPDATE guilds SET prefixes=$1::varchar[] WHERE id=$2;',
                    self.record["prefixes"], self.record["id"],
                )
        await interaction.followup.send(
            'Config successfully saved!',
            ephemeral=True,
        )

    @discord.ui.button(
        label='Close',
        row=1,
        style=discord.ButtonStyle.red,
    )
    async def close_panel(self, interaction: discord.Interaction[LegacyBot], button: discord.ui.Button[ConfigView]) -> None:
        assert interaction.guild_id
        await interaction.response.defer()
        await interaction.delete_original_response()

        cog: Configuration | None = interaction.client.get_cog('Configuration')  # pyright: ignore[reportAssignmentType]
        if cog is None:
            return
        cog.config_panels.pop(interaction.guild_id, None)
        self.stop()

    async def start(self, ctx: Context) -> 'ConfigView':
        self.message = await ctx.reply(
            embed=self.get_embed(),
            view=self,
        )
        return self


class EditWinMessage(discord.ui.Modal, title='Edit Win Message'):
    message = discord.ui.TextInput(
        label='Win Message',
        style=discord.TextStyle.short,
        required=True,
    )

    def __init__(self, *, default: str | None = None) -> None:
        super().__init__()

        self.message.default = default

    async def on_submit(self, interaction: discord.Interaction[LegacyBot]) -> None:
        self.interaction = interaction
        self.stop()


class GConfigView(discord.ui.View):
    __slots__ = (
        'claimtime',
        'premium',
        'author',
        'message',
    )

    def __init__(self, claimtime: asyncpg.Record, *, premium: bool, author: discord.abc.Snowflake) -> None:
        self.claimtime: dict[str, Any] = dict(claimtime)
        self.premium: bool = premium
        self.author: discord.abc.Snowflake = author
        self.message: discord.Message | None = None
        super().__init__(timeout=60*15)

        if claimtime["winmsg_enabled"] is True:
            self.enable_win_message.label = 'Disable'
            self.enable_win_message.style = discord.ButtonStyle.red

    async def interaction_check(self, interaction: discord.Interaction[LegacyBot]) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                'You cannot control this panel!',
                ephemeral=True,
            )
            return False
        return True

    def get_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title='Giveaway Config',
            colour=discord.Colour.blurple(),
        )
        embed.description = f'Win Message: {self.claimtime["win_message"] or "Not set"}\nWin Message Enabled: {self.claimtime["winmsg_enabled"]}'

        if self.claimtime["roles"]:
            embed.add_field(
                name='Claimtimes:',
                value='\n'.join(
                    [f'<@&{role_id}>: {claimtime["time"]:.2f} seconds | Override: {claimtime["override"]}' for role_id, claimtime in self.claimtime["roles"].items()],
                ),
            )
        return embed

    @discord.ui.button(
        label='Edit Win Message',
        style=discord.ButtonStyle.blurple,
        row=0,
    )
    async def edit_win_message(self, interaction: discord.Interaction[LegacyBot], button: discord.ui.Button[GConfigView]) -> None:
        assert interaction.guild_id
        modal = EditWinMessage(default=self.claimtime["win_message"])
        await interaction.response.send_modal(modal)
        await modal.wait()

        await modal.interaction.response.defer()

        msg = modal.message.value if modal.message.value else None

        self.claimtime["win_message"] = msg

        async with interaction.client.get_connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    'INSERT INTO claimtimes_config (guild_id, win_message) VALUES ($1, $2) ON CONFLICT (guild_id) DO UPDATE SET win_message = EXCLUDED.win_message;',
                    interaction.guild_id, self.claimtime["win_message"]
                )

        await interaction.client.claimtime_store.load()

        await interaction.edit_original_response(
            embed=self.get_embed(),
            view=self,
        )

    @discord.ui.button(
        label='Enable',
        style=discord.ButtonStyle.green,
        row=0,
    )
    async def enable_win_message(self, interaction: discord.Interaction[LegacyBot], button: discord.ui.Button[GConfigView]) -> None:
        if self.claimtime["winmsg_enabled"] is True:
            button.label = 'Enable'
            button.style = discord.ButtonStyle.green
            self.claimtime["winmsg_enabled"] = False
        else:
            button.label = 'Disable'
            button.style = discord.ButtonStyle.red
            self.claimtime["winmsg_enabled"] = True
        await interaction.response.defer()

        async with interaction.client.get_connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    'INSERT INTO claimtimes_config (guild_id, winmsg_enabled) VALUES ($1, $2) ON CONFLICT (guild_id) DO UPDATE SET winmsg_enabled = EXCLUDED.winmsg_enabled;',
                    interaction.guild_id, self.claimtime["winmsg_enabled"],
                )

        await interaction.client.claimtime_store.load()

        await interaction.edit_original_response(
            embed=self.get_embed(),
            view=self,
        )

    @discord.ui.button(
        label='Add Claimtime',
        style=discord.ButtonStyle.blurple,
        row=1,
    )
    async def add_claimtime(self, interaction: discord.Interaction[LegacyBot], button: discord.ui.Button[GConfigView]) -> None:
        assert interaction.message

        await interaction.response.send_message(
            'Choose the role to create the claimtime for:',
            view=SelectClaimtimeRoleView(self, interaction.message),
            ephemeral=True,
        )

    @discord.ui.button(
        label='Remove Claimtime',
        style=discord.ButtonStyle.red,
        row=1,
    )
    async def remove_claimtime(self, interaction: discord.Interaction[LegacyBot], button: discord.ui.Button[GConfigView]) -> None:
        assert interaction.guild
        assert interaction.message

        view = SelectRemoveClaimtimeRoleView(self.claimtime["roles"], interaction.guild)
        await interaction.response.send_message(
            'Select the roles to remove:',
            view=view,
        )

        await view.wait()
        self.claimtime["roles"] = view.roles
        await interaction.message.edit(
            embed=self.get_embed(),
            view=self,
        )

    async def start(self, ctx: Context) -> 'GConfigView':
        self.message = await ctx.reply(
            embed=self.get_embed(),
            view=self,
        )
        return self


class R:
    def __init__(self, r: int) -> None:
        self.r = r

    @property
    def name(self) -> str:
        return f'{self.r}'


class SelectRemoveClaimtimeRoleView(discord.ui.View):
    def __init__(self, roles: dict[int, dict[str, Any]], guild: discord.Guild) -> None:
        self.roles: dict[int, dict[str, Any]] = roles
        super().__init__()
        self.role_select.options = [
            discord.SelectOption(
                label=(guild.get_role(r) or R(r)).name,
                value=str(r),
            )
            for r in roles.keys()
        ]

    @discord.ui.select(placeholder='Select the roles to delete...')
    async def role_select(self, interaction: discord.Interaction[LegacyBot], select: discord.ui.Select[SelectRemoveClaimtimeRoleView]) -> None:
        await interaction.response.defer()
        guild_id = interaction.guild_id
        roles = list(map(int, select.values))

        for r in roles:
            self.roles.pop(r, None)

        async with interaction.client.get_connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    'INSERT INTO claimtimes_config (guild_id, roles) VALUES ($1, $2::jsonb) ON CONFLICT (guild_id) DO UPDATE SET roles = EXCLUDED.roles;',
                    guild_id, self.roles,
                )

        await interaction.edit_original_response(
            content='Successfully removed roles!',
            view=None,
        )
        self.stop()


class SelectClaimtimeRoleView(discord.ui.View):
    def __init__(self, parent: GConfigView, message: discord.Message) -> None:
        self.parent: GConfigView = parent
        self.message: discord.Message = message
        super().__init__()

    CONVERT_MAP = {'d': 86400, 'h': 4600, 'm': 60, 's': 1}

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        min_values=1,
        max_values=1,
        placeholder='Choose the role...',
    )
    async def role_select(
        self,
        interaction: discord.Interaction[LegacyBot],
        select: discord.ui.RoleSelect[SelectClaimtimeRoleView],
    ) -> None:
        await interaction.response.edit_message(
            content='Send the duration of the claimtime! (15s/30s/etc.) You can type ``cancel`` to cancel the process.',
            view=None,
        )

        try:
            msg = await interaction.client.wait_for(
                'message',
                check=lambda m: m.author.id == interaction.user.id and m.channel.id == interaction.channel_id,
                timeout=60.0,
            )
        except asyncio.TimeoutError:
            await interaction.edit_original_response(
                content='You took too long!',
            )
            return

        await msg.delete()

        if msg.content.lower() == 'cancel':
            await interaction.edit_original_response(
                content='Cancelled.'
            )
            return

        matches = DURATION_REGEX.findall(msg.content.lower())
        if not matches or len(matches) > 1:
            await interaction.edit_original_response(
                content='Invalid duration provided!'
            )
            return

        time, fmt = matches[0]
        value = self.CONVERT_MAP[fmt] * float(time)

        await interaction.edit_original_response(
            content='Would you like to override other claimtimes? (Y/N)',
        )

        try:
            msg = await interaction.client.wait_for(
                'message',
                check=lambda m: m.author.id == interaction.user.id and m.channel.id == interaction.channel_id,
                timeout=60.0
            )
        except asyncio.TimeoutError:
            await interaction.edit_original_response(
                content='You took too long!',
            )
            return

        await msg.delete()

        low = msg.content.lower()
        if low in ('yes', 'y', 'true', 't', '1', 'enable', 'on'):
            ret = True
        elif low in ('no', 'n', 'false', 'f', '0', 'disable', 'off'):
            ret = False
        else:
            await interaction.edit_original_response(
                content='Invalid response provided! Defaulting to ``False``.'
            )
            ret = False

        self.parent.claimtime["roles"][str(select.values[0].id)] = {"time": value, "override": ret}

        async with interaction.client.get_connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    'INSERT INTO claimtimes_config (guild_id, roles) VALUES ($1, $2::jsonb) ON CONFLICT (guild_id) DO UPDATE SET roles = EXCLUDED.roles;',
                    interaction.guild_id, self.parent.claimtime["roles"],
                )
        await interaction.client.claimtime_store.load()

        await interaction.edit_original_response(
            content='Successfully created the claimtime!',
        )

        await self.message.edit(
            embed=self.parent.get_embed(),
            view=self.parent,
        )


class Configuration(commands.Cog):
    """Commands to manage different aspects on your server."""

    def __init__(self, bot: LegacyBot) -> None:
        self.bot: LegacyBot = bot

        self.config_panels: dict[int, ConfigView] = {}
        self.gconfig_panels: dict[int, GConfigView] = {}

    async def cog_unload(self) -> None:
        for panel in self.config_panels.values():
            await panel.on_timeout()
            panel.stop()
        self.config_panels.clear()

    async def get_guild_config(self, guild: discord.Guild) -> asyncpg.Record | None:
        row = await self.bot.pool.fetchrow(
            'SELECT * FROM guilds WHERE id=$1;',
            guild.id,
        )
        return row

    async def insert_guild_config(self, guild: discord.Guild) -> asyncpg.Record:
        async with self.bot.get_connection() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    'INSERT INTO guilds ("id") VALUES ($1) RETURNING *;',
                    guild.id
                )
        if row is None:
            raise RuntimeError('row returned none')
        return row

    @commands.hybrid_command(name="config")
    @commands.has_guild_permissions(manage_guild=True)
    async def config(self, ctx: Context) -> None:
        """Manages this server config."""

        if ctx.guild.id in self.config_panels:
            await ctx.reply(
                'There is already an active panel to manage this server config!',
                ephemeral=True,
            )
            return

        config = await self.get_guild_config(ctx.guild)

        if config is None:
            config = await self.insert_guild_config(ctx.guild)

        premium = await ctx.is_premium()

        self.config_panels[ctx.guild.id] = await ConfigView(
            config,
            premium=premium,
            author=ctx.author,
        ).start(ctx)

    async def get_guild_gconfig(self, guild: discord.Guild) -> asyncpg.Record | None:
        row = await self.bot.pool.fetchrow(
            'SELECT * FROM claimtimes_config WHERE guild_id=$1;',
            guild.id,
        )
        return row

    async def insert_guild_gconfig(self, guild: discord.Guild) -> asyncpg.Record:
        async with self.bot.get_connection() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    'INSERT INTO claimtimes_config (guild_id) VALUES ($1) RETURNING *;',
                    guild.id,
                )
        if row is None:
            raise RuntimeError('row is somehow none')
        return row

    @commands.hybrid_command(name="gconfig")
    @commands.has_guild_permissions(manage_guild=True)
    async def gconfig(self, ctx: Context) -> None:
        """Manages this server giveaway config."""

        if ctx.guild.id in self.gconfig_panels:
            await ctx.reply(
                'There is already an active panel to manage giveaways config on this server!',
                ephemeral=True,
            )
            return

        config = await self.get_guild_gconfig(ctx.guild)

        if config is None:
            config = await self.insert_guild_gconfig(ctx.guild)

        premium = await ctx.is_premium()

        self.gconfig_panels[ctx.guild.id] = await GConfigView(
            config,
            premium=premium,
            author=ctx.author,
        ).start(ctx)


async def setup(bot: LegacyBot) -> None:
    await bot.add_cog(Configuration(bot))

async def teardown(bot: LegacyBot) -> None:
    await bot.remove_cog(Configuration.__cog_name__)
