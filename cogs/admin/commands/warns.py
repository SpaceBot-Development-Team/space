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
from typing import TYPE_CHECKING, Any, Dict, Optional

import discord
from discord import app_commands
from discord.ext import commands
from jishaku.shim.paginator_200 import PaginatorEmbedInterface

from _types import group
from _types.commands import command
from _types.commandutil import can_run_warn, has_permissions
from _types.views import SelectUserWarning
from _types.warns import Warn
from models import GuildUser

if TYPE_CHECKING:
    from _types import Bot, GuildContext

WARN_STRING = """
**ID:** `{warn_id}`
**Staff Responsable:** <@{staff}> ({staff})
**Razón:** {reason}

"""


class CustomPaginatorInterface(PaginatorEmbedInterface):
    async def send_to(self, dest: GuildContext) -> CustomPaginatorInterface:  # type: ignore
        self.message = await dest.send(
            **self.send_kwargs,
            allowed_mentions=discord.AllowedMentions.none(),
        )

        self.send_lock.set()

        if self.task:
            self.task.cancel()

        self.task = self.bot.loop.create_task(self.wait_loop())

        return self


class WarnsCommands:

    def __init__(self, bot: Bot) -> None:
        self.bot: Bot = bot

    @group(
        name="warn",
        fallback="add",
    )
    @can_run_warn()
    @has_permissions(moderate_members=True)
    @app_commands.describe(
        member="El miembro que sancionar",
        reason="La razón por la que fue sancionado",
    )
    async def warn_add(
        self,
        ctx: GuildContext,
        member: discord.Member,
        *,
        reason: str = "Advertencia",
    ):
        """Añade una advertencia al usuario proporcionado."""

        if member.top_role > ctx.author.top_role:
            return await ctx.reply(
                "No puedes gestionar a este usuario",
                ephemeral=True,
                delete_after=5,
            )
        cfg, _ = await GuildUser.get_or_create(guild=ctx.guild.id, user=member.id)

        warn_id = str(uuid.uuid4())
        warn_data: Dict[str, Warn] = {
            warn_id: Warn.from_data(
                id=warn_id,
                data={
                    "created_at": discord.utils.utcnow().isoformat(),
                    "author": ctx.author.id,
                    "target": member.id,
                    "guild_id": ctx.guild.id,
                    "reason": reason,
                },
                state=ctx._state,
            )
        }

        if not cfg.warns:
            cfg.warns = warn_data
        else:
            cfg.warns.update(warn_data)  # type: ignore

        content = f"Se ha añadido la advertencia `{warn_id}` a {member.mention}, quién ahora tiene {len(cfg.warns.keys())} advertencias"  # type: ignore

        await ctx.reply(content)
        await cfg.save()
        self.bot.dispatch(
            "warn_add",
            Warn(
                id=warn_id,
                guild=ctx.guild,
                target=member,
                staff=ctx.author,
                reason=reason,
            ),
        )

    @warn_add.command(name="remove")
    @can_run_warn()
    @has_permissions(moderate_members=True)
    @app_commands.describe(
        member="El miembro al que quitar la advertencia",
        id="La ID de la advertencia que quitar",
    )
    async def warn_remove(
        self,
        ctx: GuildContext,
        member: discord.Member,
        *,
        id: Optional[str] = None,
    ) -> Any:
        """Quita una advertencia de un miembro."""
        user = await GuildUser.get_or_none(guild=ctx.guild.id, user=member.id)

        if not user or not user.warns or len(user.warns.keys()) == 0:
            return await ctx.reply(
                "Este usuario no tiene advertencias", ephemeral=True, delete_after=5
            )

        if id:
            if id not in user.warns:
                return await ctx.reply(
                    f"Este usuario no tiene una advertencia con ID `{id}`",
                    ephemeral=True,
                    delete_after=5,
                )

            warn = user.warns.pop(id)

            await ctx.reply(
                f"Se ha quitado la advertencia con ID `{id}` de {member.mention}. Su razón fue: `{warn.reason}`"
            )
            await user.save()
            new = Warn.from_data(id=id, data=warn.to_dict(), state=ctx._state)
            self.bot.dispatch("warn_remove", new)
            return

        view = SelectUserWarning(user, ctx.author)
        await ctx.reply("Selecciona la advertencia que quieres quitar", view=view)

    @command(name="warnings", aliases=["warns"])
    @can_run_warn()
    @has_permissions(manage_guild=True)
    async def _warnings(
        self, ctx: GuildContext, *, member: discord.Member = commands.Author
    ) -> Any:
        """Comprueba las advertencias de un miembro, o tuyas.

        Parameters
        ----------
        member: Miembro
            El miembro del que ver las advertencias, o tú.
        """

        async with ctx.typing():
            user = await GuildUser.get_or_none(guild=ctx.guild.id, user=member.id)

        if not user:
            return await ctx.reply("Este usuario no tiene advertencias", ephemeral=True)

        paginator = commands.Paginator(
            None,
            None,
            PaginatorEmbedInterface.max_page_size,
        )
        interface = CustomPaginatorInterface(
            self.bot,
            paginator,
            owner=ctx.author,
            delete_message=True,
        )
        await interface.add_line("")

        for warn_id, data in user.warns.items():
            await interface.add_line(
                WARN_STRING.format(
                    warn_id=warn_id, staff=data.staff.id, reason=data.reason
                )
            )

        if not interface.pages:
            return await ctx.reply("Este usuario no tiene advertencias", ephemeral=True)

        await interface.send_to(ctx)
