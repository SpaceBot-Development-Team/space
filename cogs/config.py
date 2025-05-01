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
import math
import re
from typing import TYPE_CHECKING, Any
from collections.abc import Iterable

import asyncpg
import discord
from discord.ext import commands, tasks

if TYPE_CHECKING:
    from typing import TypedDict

    from bot import LegacyBot, LegacyBotContext as Context

    Interaction = discord.Interaction[LegacyBot]

    class GreetData(TypedDict):
        message: str
        delafter: float

    class ConfigRecord(TypedDict):
        id: int
        prefixes: list[str]
        greets: dict[str, GreetData]
        messages_enabled: bool
        disabled_modules: list[str]

PREMIUM_SKU_ID = 1256218013930094682
DURATION_REGEX = re.compile(r'(\d{1,5}(?:[.,]?\d{1,5})?)([smhd])')


def replace_greet_message_vars(string: str, member: discord.Member) -> str:
    return string.replace(
        "{mention}",
        member.mention,
    ).replace(
        "{mc}",
        str(
            member.guild.member_count
            or member.guild.approximate_member_count
            or len(member.guild.members)
        ),
    ).replace(
        '{server_name}', member.guild.name,
    ).replace(
        '{member(tag)}', member.name,
    ).replace(
        '{member(name)}', member.display_name,
    )


class AddPrefixModal(discord.ui.Modal, title='Add A Prefix'):
    prefix = discord.ui.TextInput(
        label='Prefix',
        style=discord.TextStyle.short,
        max_length=15,
        min_length=1,
        required=True,
    )

    async def on_submit(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        self.interaction = interaction
        self.stop()


class EditGreetDelafterModal(discord.ui.Modal, title='Change Delete After'):
    delafter = discord.ui.TextInput(
        label='Delete After',
        style=discord.TextStyle.short,
        max_length=4,
        min_length=1,
        required=True,
    )

    def __init__(self, default: str | None) -> None:
        super().__init__()
        self.delafter.default = default

    async def on_submit(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        self.interaction = interaction
        self.stop()


class ConfigViewPrefixesActionRow(discord.ui.ActionRow['ConfigView']):
    def __init__(self) -> None:
        super().__init__()

    @discord.ui.button(label='Add Prefix', style=discord.ButtonStyle.blurple)
    async def add_prefix(self, interaction: Interaction, button: discord.ui.Button['ConfigView']) -> None:
        assert self.view

        self.view.update_premium(interaction)

        prefixes = self.view.record['prefixes']

        if len(prefixes) >= 3 and not self.view.premium:
            await interaction.response.send_message(
                'You have reached the limit of 3 prefixes on the Free Plan!\nBuy [Space] Premium to unlock up to 5 prefixes!',
                view=self.view.construct_buy_premium_view(),
            )
            return
        elif len(prefixes) >= 5 and self.view.premium:
            await interaction.response.send_message(
                'You have reached the limit of 5 prefixes!',
                view=self.view.construct_buy_premium_view(),
            )
            return

        modal = AddPrefixModal()
        await interaction.response.send_modal(modal)
        await modal.wait()

        prefix = modal.prefix.value

        if not prefix:
            await modal.interaction.followup.send(
                'Non-valid prefix provided!',
                ephemeral=True,
            )
            return

        self.view.record['prefixes'].append(prefix)

        self.pop_prefix.disabled = False
        self.save_prefixes.disabled = False

        if len(prefixes) + 1 >= 3 and not self.view.premium:
            button.disabled = True
        elif len(prefixes) + 1 >= 5 and self.view.premium:
            button.disabled = True

        await interaction.edit_original_response(view=self.view.update_self())

    @discord.ui.button(label='Remove Last Prefix', style=discord.ButtonStyle.red)
    async def pop_prefix(self, interaction: Interaction, button: discord.ui.Button['ConfigView']) -> None:
        assert self.view

        await interaction.response.defer()
        self.view.update_premium(interaction)

        try:
            self.view.record['prefixes'].pop()
        except IndexError:
            await interaction.response.send_message('You cannot remove any more prefixes!', ephemeral=True)
            return

        self.add_prefix.disabled = False

        if len(self.view.record['prefixes']) < 1:
            button.disabled = True
            self.save_prefixes.disabled = True

        await interaction.edit_original_response(view=self.view.update_self())

    @discord.ui.button(label='Save Prefixes', style=discord.ButtonStyle.green)
    async def save_prefixes(self, interaction: Interaction, button: discord.ui.Button['ConfigView']) -> None:
        assert self.view

        if len(self.view.record['prefixes']) < 1:
            await interaction.response.send_message(
                'You need at least 1 prefix to save!',
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        async with interaction.client.get_connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    'UPDATE guilds SET prefixes = $1::varchar[] WHERE "id" = $2;',
                    self.view.record['prefixes'], interaction.guild_id,
                )

        await interaction.edit_original_response(view=self.view.update_self())
        await interaction.followup.send('Prefixes successfully saved!', ephemeral=True)


class ConfigViewGreetActionRow(discord.ui.ActionRow['ConfigView']):
    def __init__(self) -> None:
        super().__init__()

    @discord.ui.button(label='Edit Greet Message', style=discord.ButtonStyle.blurple)
    async def edit_greet_message(self, interaction: Interaction, button: discord.ui.Button['ConfigView']) -> None:
        assert self.view

        modal = EditGreetMessage(self.view.get_greet_message())
        await interaction.response.send_modal(modal)
        await modal.wait()
        msg = modal.message.value

        if not msg:
            await modal.interaction.followup.send(
                'Non-valid message provided!',
                ephemeral=True,
            )
            return

        pd: GreetData = {'message': msg, 'delafter': self.view.get_greet_delafter()}
        keys = self.view.record['greets'].keys() if len(self.view.record['greets']) > 0 else ['0']

        for key in keys:
            self.view.record['greets'][key] = pd

        async with interaction.client.get_connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    'UPDATE guilds SET greets = $1::jsonb WHERE "id" = $2;',
                    self.view.record['greets'], interaction.guild_id,
                )

        await interaction.edit_original_response(view=self.view.update_self())

    @discord.ui.button(label='Change Delete After', style=discord.ButtonStyle.blurple)
    async def edit_greet_delafter(self, interaction: Interaction, button: discord.ui.Button['ConfigView']) -> None:
        assert self.view

        modal = EditGreetDelafterModal(str(self.view.get_greet_delafter()))
        await interaction.response.send_modal(modal)
        await modal.wait()
        delafter = modal.delafter.value

        if not delafter:
            await modal.interaction.followup.send(
                'Non-valid delete after value provided!',
                ephemeral=True,
            )
            return

        try:
            res = float(delafter.replace(',', '.').strip())
        except ValueError:
            await modal.interaction.followup.send(
                'Non-valid delete after value provided!',
                ephemeral=True,
            )
            return

        if res in (math.inf, -math.inf, math.nan):
            await modal.interaction.followup.send(
                'You cannot provide infinite nor Not-A-Number s on greet delete after!',
                ephemeral=True,
            )
            return

        pd: GreetData = {'message': self.view.get_greet_message(), 'delafter': res}
        keys = self.view.record['greets'].keys() if len(self.view.record['greets']) > 0 else ['0']

        for key in keys:
            self.view.record['greets'][key] = pd

        async with interaction.client.get_connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    'UPDATE guilds SET greets = $1::jsonb WHERE "id" = $2;',
                    self.view.record['greets'], interaction.guild_id,
                )

        await interaction.edit_original_response(view=self.view.update_self())


class ConfigView(discord.ui.LayoutView):
    __slots__ = (
        'record',
        'premium',
        'author',
        'message',
        'bot',
        'prefix',
    )

    def __init__(self, record: asyncpg.Record, context: Context, *, premium: bool) -> None:
        self.record: ConfigRecord = dict(record)  # pyright: ignore[reportAttributeAccessIssue]
        self.premium: bool = premium
        self.author: discord.abc.Snowflake = context.author
        self.message: discord.Message | None = None
        self.bot: LegacyBot = context.bot
        self.ctx: Context = context

        prefixes = self.record.get('prefixes')
        if prefixes is None:
            prefixes = self.record['prefixes'] = ['?']

        super().__init__(timeout=60*15)  # 15 minutes

        self.info_container = discord.ui.Container(accent_colour=discord.Colour.blurple())
        self.prefixes_action_row = ConfigViewPrefixesActionRow()
        self.greets_action_row = ConfigViewGreetActionRow()

        if len(prefixes) >= 3 and not premium:
            self.prefixes_action_row.add_prefix.disabled = True
        elif len(prefixes) >= 5 and premium:
            self.prefixes_action_row.add_prefix.disabled = True

        self.update_self()

    async def on_timeout(self) -> None:
        for child in self.walk_children():
            if hasattr(child, 'disabled'):
                child.disabled = True

        if self.message:
            await self.message.edit(view=self)

    async def start(self) -> ConfigView:
        self.message = await self.ctx.reply(view=self)
        return self

    def get_greet_message(self) -> str:
        ret = 'Welcome {mention} to {server_name}'
        if greets := self.record['greets']:
            if len(greets) > 0:
                ret = tuple(v['message'] for v in greets.values())[0]
        return ret

    def get_greet_delafter(self) -> float:
        ret = 5.0
        if greets := self.record['greets']:
            if len(greets) > 0:
                ret = tuple(v['delafter'] for v in greets.values())[0]
        return ret

    def construct_buy_premium_view(self) -> discord.ui.View:
        return discord.ui.View(timeout=.1).add_item(discord.ui.Button(sku_id=PREMIUM_SKU_ID))

    def update_premium(self, interaction: Interaction):
        self.premium = (PREMIUM_SKU_ID in interaction.entitlement_sku_ids) or (discord.utils.get(interaction.entitlements, sku_id=PREMIUM_SKU_ID) is not None)

    def update_self(self) -> 'ConfigView':
        self.clear_items()
        self.info_container.clear_items()

        greet_message = self.get_greet_message()
        greet_delafter = self.get_greet_delafter()
        greets = self.record['greets']

        modules = '```ansi\n'

        for cog in self.bot.cogs.values():
            disabled = cog.qualified_name in self.record['disabled_modules']

            if disabled:
                colour = '\u001b[0;31m'
            else:
                colour = '\u001b[0;32m'

            modules += colour + f'{cog.qualified_name}\u001b[0m, '

        modules = modules.strip().removesuffix(',') + '```'

        # -- prefixes --
        self.info_container.add_item(
            discord.ui.TextDisplay(
                (
                    f'# Server Config\n\n'
                    f'**Prefixes:** {", ".join(f"``{pre}``" for pre in self.record["prefixes"])}'
                ),
            ),
        )
        self.info_container.add_item(
            self.prefixes_action_row,
        )
        self.info_container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSize.small)
        )

        # -- greet --
        self.info_container.add_item(
            discord.ui.TextDisplay(
                f'**Greet Channels:** {", ".join(f"<#{ch}>" for ch in greets.keys())}\n'
                f'**Greet Message:** {greet_message}\n**Delete Greet Message After:** {greet_delafter}'
            ),
        )
        self.info_container.add_item(
            self.greets_action_row,
        )
        self.info_container.add_item(
            discord.ui.ActionRow(ModifyGreetChannelsSelect(greets.keys(), self.premium)),
        )
        self.info_container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSize.small)
        )

        # -- modules --

        self.info_container.add_item(
            discord.ui.TextDisplay(
                '**Modules:** toggle modules by using the selector below. If you select a module that is enabled, then it gets disabled; '
                'if you select a module that is disabled, then it gets enabled.',
            ),
        )
        self.info_container.add_item(
            discord.ui.ActionRow(ToggleModulesSelect(self.record['disabled_modules'], self.bot)),
        )

        return self

    async def interaction_check(self, interaction: Interaction) -> bool:
        if not interaction.user.id == self.author.id:
            await interaction.response.send_message('You cannot control this panel!', ephemeral=True)
            return False
        return True


class ToggleModulesSelect(discord.ui.Select['ConfigView']):
    ENABLED = discord.PartialEmoji.from_str('<:toggle_on:1367605532050853919>')
    DISABLED = discord.PartialEmoji.from_str('<:toggle_off:1367605704680276110>')

    def __init__(self, disabled_modules: list[str], bot: LegacyBot) -> None:
        options = []

        for cog in bot.cogs.values():
            options.append(
                discord.SelectOption(
                    label=cog.qualified_name,
                    emoji=self.DISABLED if cog.qualified_name in disabled_modules else self.ENABLED,
                    description=cog.description,
                ),
            )

        self.disabled_modules: list[str] = disabled_modules

        super().__init__(
            placeholder='Choose the modules to disable or enable...',
            min_values=1,
            max_values=len(bot.cogs),
            options=options,
            disabled=False,
        )

    async def callback(self, interaction: Interaction) -> None:
        assert self.view
        assert interaction.guild_id

        await interaction.response.defer()
        self.view.update_premium(interaction)

        for cog in self.values:
            if cog in self.disabled_modules:
                self.disabled_modules.remove(cog)
            else:
                self.disabled_modules.append(cog)

        await interaction.client.update_disabled_modules(interaction.guild_id, self.disabled_modules)
        await interaction.edit_original_response(view=self.view.update_self())


class ModifyGreetChannelsSelect(discord.ui.ChannelSelect['ConfigView']):
    def __init__(self, default_channels: Iterable[str | int], premium: bool, /) -> None:
        super().__init__(
            channel_types=[
                discord.ChannelType.text,
                discord.ChannelType.news_thread,
                discord.ChannelType.public_thread,
                discord.ChannelType.private_thread,
                discord.ChannelType.voice,
            ],
            default_values=[
                discord.SelectDefaultValue.from_channel(discord.Object(int(c)))
                for c in default_channels
            ],
            min_values=0,
            max_values=10 if premium else 5,
        )

    async def callback(self, interaction: Interaction) -> None:
        assert self.view

        await interaction.response.defer()
        self.view.update_premium(interaction)

        if not self.values:
            self.view.record['greets'] = {
                '0': {'message': self.view.get_greet_message(), 'delafter': self.view.get_greet_delafter()},
            }
        else:
            payload: GreetData = {'message': self.view.get_greet_message(), 'delafter': self.view.get_greet_delafter()}
            for ch in self.values:
                self.view.record['greets'][str(ch.id)] = payload

        async with interaction.client.get_connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    'UPDATE guilds SET greets = $1::jsonb WHERE "id" = $2;',
                    self.view.record['greets'], interaction.guild_id,
                )

        await interaction.edit_original_response(view=self.view.update_self())


class EditGreetMessage(discord.ui.Modal, title='Edit Greet Message'):
    message = discord.ui.TextInput(
        label='Greet Message',
        style=discord.TextStyle.short,
        required=True,
    )

    def __init__(self, default: str | None = None) -> None:
        super().__init__()

        self.message.default = default

    async def on_submit(self, interaction: Interaction) -> None:
        self.interaction = interaction
        await interaction.response.defer()
        self.stop()


class EditWinMessage(discord.ui.Modal, title='Edit Win Message'):
    message = discord.ui.TextInput(
        label='Win Message',
        style=discord.TextStyle.short,
        required=True,
    )

    def __init__(self, *, default: str | None = None) -> None:
        super().__init__()

        self.message.default = default

    async def on_submit(self, interaction: Interaction) -> None:
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

    async def interaction_check(self, interaction: Interaction) -> bool:
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
    async def edit_win_message(self, interaction: Interaction, button: discord.ui.Button[GConfigView]) -> None:
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
    async def enable_win_message(self, interaction: Interaction, button: discord.ui.Button[GConfigView]) -> None:
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
    async def add_claimtime(self, interaction: Interaction, button: discord.ui.Button[GConfigView]) -> None:
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
    async def remove_claimtime(self, interaction: Interaction, button: discord.ui.Button[GConfigView]) -> None:
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
    async def role_select(self, interaction: Interaction, select: discord.ui.Select[SelectRemoveClaimtimeRoleView]) -> None:
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
        interaction: Interaction,
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
        self.greets_cache: dict[int, dict[str, GreetData]] = {}

        self.load_and_cache_configs.start()

    async def cog_unload(self) -> None:
        for panel in self.config_panels.values():
            await panel.on_timeout()
            panel.stop()
        self.config_panels.clear()

        for panel in self.gconfig_panels.values():
            await panel.on_timeout()
            panel.stop()
        self.gconfig_panels.clear()

        self.load_and_cache_configs.cancel()
        self.greets_cache.clear()

    async def get_guilds_config(self) -> list[asyncpg.Record]:
        rows = await self.bot.pool.fetch(
            'SELECT * FROM guilds;',
        )
        return rows

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

    @tasks.loop(seconds=30)
    async def load_and_cache_configs(self) -> None:
        rows = await self.get_guilds_config()

        for row in rows:
            self.greets_cache[int(row['id'])] = row['greets']

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        guild_id = member.guild.id
        greet = self.greets_cache.get(guild_id)

        if greet is None:
            return

        for ch, data in greet.items():
            partial = self.bot.get_partial_messageable(
                int(ch),
                guild_id=member.guild.id,
            )
            msg = data['message']
            delafter = data['delafter']

            try:
                await partial.send(
                    replace_greet_message_vars(msg, member),
                    delete_after=delafter,
                )
            except discord.HTTPException:
                pass

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

        view = ConfigView(config, ctx, premium=premium)

        self.config_panels[ctx.guild.id] = await view.start()

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
