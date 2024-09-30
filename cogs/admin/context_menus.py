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

import uuid
from typing import TYPE_CHECKING, Any

from _types.contextutil import ContextMenuHolder, context_menu
from _types.bot import Bot
from _types.warns.models import WarnConfig
from models import WarnsConfig, GuildUser

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from _types.interactions import GuildInteraction


class AdminContextMenus(commands.Cog):
    """..."""

    def __init__(self, bot: Bot) -> None:
        self.bot: Bot = bot
        self._context_menu_holder = ContextMenuHolder.partial_holder()
        self._context_menu_holder.on_attach = self.on_attach

    async def on_attach(self) -> None:
        """Called when the context menu holder gets attached"""
        self._context_menu_holder.load_commands_from(self)

    async def cog_load(self) -> None:
        self._context_menu_holder.attach(self.bot)
        self._context_menu_holder.copy_to_tree()

    @context_menu(
        name="Advertir Usuario",
    )
    @app_commands.default_permissions(
        moderate_members=True,
    )
    @app_commands.guild_only()
    async def warn_user(
        self,
        interaction: GuildInteraction,
        user: discord.Member,
    ) -> Any:
        """Añade una advertencia al usuario."""

        if user.top_role > interaction.user.top_role:
            return await interaction.response.send_message(
                "No puedes gestionar a este usuario.",
                ephemeral=True,
            )
        await interaction.response.defer(
            ephemeral=True,
            thinking=True,
        )
        config, _ = await WarnsConfig.get_or_create(
            {"enabled": False, "config": WarnConfig.empty(), "notifications": None},
            id=interaction.guild_id,
        )

        if not config.enabled:
            return await interaction.followup.send(
                "No se han habilitado las advertencias",
                ephemeral=True,
            )

        user_config, _ = await GuildUser.get_or_create(
            {"warns": {}},
            user=user.id,
            guild=interaction.guild_id,
        )

        warn_id = str(uuid.uuid4())
        warn = {
            "created_at": discord.utils.utcnow().isoformat(),
            "author": interaction.user.id,
            "reason": "Advertencia",
            "target": user.id,
            "guild_id": interaction.guild_id,
        }

        user_warns = user_config.warns

        if not user_warns:
            user_warns = {}

        user_warns.update(
            {
                warn_id: warn,
            }
        )

        user_config.warns = user_warns

        content = (
            f"Se ha añadido la advertencia `{warn_id}` a {user.mention}, "
            f"quien ahora tiene {len(user_config.warns)} advertencias."
        )

        await user_config.save()
        await interaction.followup.send(
            content,
            ephemeral=True,
        )

        self.bot.dispatch(
            "warn_add",
            user,
            interaction.user,
            {warn_id: warn},
            config,
        )
