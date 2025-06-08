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

from typing import TYPE_CHECKING, Annotated, Literal

import discord
from discord.ext import commands

from utils import format_td

if TYPE_CHECKING:
    from bot import LegacyBot, LegacyBotContext as Context

    Interaction = discord.Interaction[LegacyBot]

Object = Annotated[discord.Object, commands.ObjectConverter]


class UpdateObjectModal(discord.ui.Modal, title='Update ID'):
    id_field = discord.ui.TextInput(
        label='Update ID:',
        style=discord.TextStyle.short,
        min_length=15,
        max_length=21,
        required=True,
        placeholder='123456789012345...',
    )

    async def on_submit(self, interaction: Interaction) -> None:
        await interaction.response.defer()


class EditObjectButton(discord.ui.Button['TimeDiffView']):
    def __init__(self, original: discord.Object, obj: Literal['1', '2'], *, disabled: bool = False) -> None:
        self.original: discord.Object = original
        self.obj: Literal['1', '2'] = obj
        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Edit ID',
            disabled=disabled,
        )

    async def callback(self, interaction: Interaction) -> None:
        modal = UpdateObjectModal()
        modal.id_field.default = str(self.original.id)
        await interaction.response.send_modal(modal)
        await modal.wait()

        if not modal.id_field.value.isdigit():
            await interaction.followup.send(f'ID "{modal.id_field.value}" is not valid!', ephemeral=True)
            return

        if not self.view:
            await interaction.followup.send('This request could not be proccessed, try again later.', ephemeral=True)
            return

        self.original = discord.Object(int(modal.id_field.value))

        if self.obj == '1':
            self.view.object_1 = self.original
        elif self.obj == '2':
            self.view.object_2 = self.original

        await self.view.update_message()


class TimeDiffView(discord.ui.LayoutView):
    def __init__(self, object_1: discord.Object, object_2: discord.Object, author: discord.abc.User) -> None:
        super().__init__()

        self.object_1: discord.Object = object_1
        self.object_2: discord.Object = object_2
        self.message: discord.Message | None = None
        self.author: discord.abc.User = author

        self.object_container = discord.ui.Container(
            accent_colour=discord.Colour.blurple(),
        )
        self.update_container()

        self.add_item(self.object_container)

    async def on_timeout(self) -> None:
        if self.message:
            self.update_container(disable_buttons=True)
            await self.message.edit(view=self)

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.message:
            self.message = interaction.message

        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                'This items cannot be clicked by you!',
                ephemeral=True,
            )
            return False
        return True

    async def update_message(self) -> None:
        if not self.message:
            return

        self.update_container()
        await self.message.edit(view=self)

    def update_container(self, *, disable_buttons: bool = False) -> None:
        self.object_container._children = []

        diff = self.object_2.created_at - self.object_1.created_at

        self.object_container.add_item(
            discord.ui.TextDisplay(
                f'Difference between both IDs: {format_td(diff)}',
            ),
        )

        section1 = discord.ui.Section(
            discord.ui.TextDisplay(
                f'ID 1: {self.object_1.id} | Created at: {discord.utils.format_dt(self.object_1.created_at)}'
            ),
            accessory=EditObjectButton(self.object_1, '1', disabled=disable_buttons),
        )
        section2 = discord.ui.Section(
            discord.ui.TextDisplay(
                f'ID 2: {self.object_2.id} | Created at: {discord.utils.format_dt(self.object_2.created_at)}'
            ),
            accessory=EditObjectButton(self.object_2, '2', disabled=disable_buttons),
        )

        self.object_container.add_item(discord.ui.Separator(visible=True))
        self.object_container.add_item(section1)
        self.object_container.add_item(discord.ui.Separator(visible=True))
        self.object_container.add_item(section2)


class Tools(commands.Cog):
    """Some utility commands that may be useful for you."""

    def __init__(self, bot: LegacyBot) -> None:
        self.bot: LegacyBot = bot

    @commands.hybrid_command(name='nuke')
    @commands.has_guild_permissions(manage_channels=True)
    @commands.cooldown(1, 30, commands.BucketType.member)
    async def nuke(self, ctx: Context, *, channel: discord.TextChannel = commands.CurrentChannel) -> None:
        """Nukes a channel. Which esentially clones it, moves it to its position, and deletes the old one.

        Parameters
        ----------
        channel:
            The channel to nuke.
        """

        if ctx.interaction:
            await ctx.interaction.response.defer(thinking=True, ephemeral=True)

        ch = await channel.clone(reason=f'Nuke by {ctx.author} (ID: {ctx.author.id})')
        await channel.delete(reason=f'Nuke by {ctx.author} (ID: {ctx.author.id})')
        await ch.edit(position=channel.position)

    @commands.hybrid_command(name='timediff', aliases=['timedif', 'snowflake'])
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def timediff(self, ctx: Context, object_1: Object, *, object_2: Object | None = None) -> None:
        """Checks the difference between 2 Discord IDs.

        Parameters
        ----------
        object_1:
            The first object to compare.
        object_2:
            The second object to compare.
        """

        if object_2 is None:
            if ctx.reference is None:
                await ctx.reply(
                    'You need to provide a second ID or reply to a message to compare both objects.',
                    ephemeral=True,
                )
                return

            if ctx.reference.message_id is None:
                await ctx.reply(
                    'The replied message ID was somehow None, try again later!',
                    ephemeral=True,
                )
                return

            object_2 = discord.Object(ctx.reference.message_id)

        view = TimeDiffView(object_1, object_2, ctx.author)
        await ctx.reply(view=view)


async def setup(bot: LegacyBot) -> None:
    await bot.add_cog(Tools(bot))


async def teardown(bot: LegacyBot) -> None:
    await bot.remove_cog(Tools.__cog_name__)
