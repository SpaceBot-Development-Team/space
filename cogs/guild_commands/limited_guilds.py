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

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from _types import GuildContext, GuildInteraction

if TYPE_CHECKING:
    from _types import Bot

POSEIDON_ID, SUPPORT_SERVER_ID = AVAILABLE_GUILD_IDS = (
    1221246473493151765,
    1002610050860339221,
)
POSEIDON, SUPPORT_SERVER = AVAILABLE_GUILDS = tuple(
    map(discord.Object, AVAILABLE_GUILD_IDS)
)
POSEIDON_INACTIVITY_CHANNEL_ID, SUPPORT_SERVER_INACTIVITY_CHANNEL_ID = (
    INACTIVITY_CHANNEL_IDS
) = (1292243973892476958, 1216387369360560218)
POSEIDON_INACTIVITY_CHANNEL, SUPPORT_SERVER_INACTIVITY_CHANNEL = INACTIVITY_CHANNELS = (
    tuple(map(discord.Object, INACTIVITY_CHANNEL_IDS))
)


class InactividadModal(discord.ui.Modal):
    """Represents a modal sent in the ``/inactividad`` command.

    The channel where the notification is sent changes based of the guild it was invoked
    from.
    """

    def __init__(self, guild_id: int, client: Bot, /) -> None:
        self.guild_id: int = guild_id
        self.client: Bot = client
        super().__init__(title="Justificar Inactividad")

        self.reason: discord.ui.TextInput["InactividadModal"] = discord.ui.TextInput(
            label="Motivo",
            style=discord.TextStyle.long,
            placeholder="Voy a estar inactivo debido a...",
            required=True,
            min_length=5,
            max_length=2000,
        )
        self.duration: discord.ui.TextInput["InactividadModal"] = discord.ui.TextInput(
            label="Duración de la inactividad",
            style=discord.TextStyle.short,
            placeholder="1 día...",
            required=False,
            default="Indefinido",
            min_length=2,
            max_length=50,
        )
        self.add_item(self.reason)
        self.add_item(self.duration)

    async def on_submit(self, interaction: GuildInteraction[Bot]) -> None:  # type: ignore
        await interaction.response.defer(ephemeral=True, thinking=True)
        embed = self.generate_embed()
        embed.set_author(
            name=str(interaction.user), icon_url=interaction.user.display_avatar.url
        )
        await self.channel.send(embed=embed)
        await interaction.followup.send(
            "Se ha justificado tu inactividad.", ephemeral=True
        )

    def generate_embed(self) -> discord.Embed:
        """:class:`discord.Embed`: Constructs an embed based of the data provided on the submit."""
        embed = discord.Embed(
            color=self.client.default_color,
            title="Justificación de inactividad",
        )
        embed.add_field(
            name="Motivo de inactividad:",
            value=self.reason.value,
            inline=True,
        )
        embed.add_field(
            name="Duración de inactividad:",
            value=self.duration.value,
            inline=True,
        )
        return embed

    @property
    def channel(self) -> discord.PartialMessageable:
        """:class:`discord.PartialMessageable`: The channel to send the notification to."""
        if self.guild_id == POSEIDON_ID:
            return self.client.get_partial_messageable(
                POSEIDON_INACTIVITY_CHANNEL.id, guild_id=POSEIDON_ID
            )
        elif self.guild_id == SUPPORT_SERVER_ID:
            return self.client.get_partial_messageable(
                SUPPORT_SERVER_INACTIVITY_CHANNEL.id, guild_id=SUPPORT_SERVER_ID
            )
        else:
            raise ValueError("Invalid guild ID provided")


class SupportServer(commands.Cog):
    """Support commands specific commands"""

    def __init__(self, bot: Bot) -> None:
        self.bot: Bot = bot

    async def cog_check(self, ctx: GuildContext) -> bool:  # type: ignore
        return ctx.guild.id in AVAILABLE_GUILD_IDS

    @app_commands.command(name="inactividad")  # type: ignore
    @app_commands.guilds(*AVAILABLE_GUILDS)
    async def inactividad(self, interaction: GuildInteraction) -> None:
        """Justifica un periodo de inactividad"""
        await interaction.response.send_modal(
            InactividadModal(interaction.guild_id, interaction.client)
        )


async def setup(bot: Bot) -> None:
    """Loads all the cogs in this module"""
    await bot.add_cog(SupportServer(bot))
