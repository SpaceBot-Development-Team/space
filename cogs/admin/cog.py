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

# type: ignore
# pylint: disable=wrong-import-order, missing-function-docstring, protected-access, missing-class-docstring

import discord

from _types import (
    Bot,
    group,
    command,
    EmbedBuilderView,
    GuildContext,
)

from discord.ext import commands
from discord.ext.commands.cog import Cog
from discord.ext.commands.core import has_guild_permissions, check
from discord.ext.commands.converter import MessageConverter
from discord.ext.commands.errors import MessageNotFound, ChannelNotReadable
from discord.app_commands.commands import default_permissions
from discord.app_commands.translator import locale_str as locale

from typing import Any, ClassVar, Optional, TypeVar

from sessions import (
    ConfigSession,
    StrikesConfigSession,
    WarnsConfigSession,
)
from models import Guild, WarnsConfig
from .commands.strikes import StrikesCommands


T = TypeVar("T")


def can_run_strike():
    async def predicate(ctx: GuildContext) -> bool:
        if not ctx.guild:
            raise commands.NoPrivateMessage(
                "Este comando no se puede utilizar fuera de serivdores"
            )
        if not await Guild.exists(id=ctx.guild.id):
            return False
        cfg = await Guild.get(id=ctx.guild.id)

        return cfg.staff_report is not None and cfg.user_report is not None

    return check(predicate)


def can_run_warn():
    async def predicate(ctx: GuildContext) -> bool:
        if not ctx.guild:
            raise commands.NoPrivateMessage(
                "Este comando no se puede utilizar fuera de servidores"
            )
        if not await WarnsConfig.exists(id=ctx.guild.id):
            return False
        cfg = await WarnsConfig.get(id=ctx.guild.id)

        return cfg.enabled

    return check(predicate)


class StrikeAddFlags(commands.FlagConverter, prefix="--", delimiter=" "):
    reason: str = commands.flag(
        positional=True, description="La razón por la que añades el strike"
    )
    note: Optional[str] = commands.flag(
        default=None, description="La nota que añadir como pie de embed."
    )


class Admin(StrikesCommands, Cog):
    """Comandos para administradores."""

    CONTRAST_COLOR: ClassVar[discord.Color] = discord.Color.from_str("#755ae0")

    def __init__(self, bot: Bot) -> None:
        super().__init__(bot)
        self.bot: Bot = bot

    @group(fallback="bot", description=locale("Configura el bot en tu servidor"))
    @has_guild_permissions(manage_guild=True)
    @default_permissions(manage_guild=True)
    async def setup(self, ctx: GuildContext) -> Any:
        session = await ConfigSession.from_context(ctx)

        await session.start()

    @setup.command(
        name="strikes",
        aliases=["sanctions", "reports"],
        description=locale("Configura los strikes"),
    )
    @has_guild_permissions(manage_guild=True)
    @default_permissions(manage_guild=True)
    async def setup_strikes(self, ctx: GuildContext) -> Any:
        session = await StrikesConfigSession.from_context(ctx)

        await session.start()

    @setup.command(
        name="warns",
        description=locale("Configura las advertencias"),
    )
    @has_guild_permissions(manage_guild=True)
    @default_permissions(manage_guild=True)
    async def setup_warns(self, ctx: GuildContext) -> Any:
        session = await WarnsConfigSession.from_context(ctx)
        await session.start()

    @staticmethod
    def generate_help_embed() -> discord.Embed:
        emb = discord.Embed(
            title="Título",
            url="http://example.com/orbyt",
            description="Esta es la _descripción_ del embed.\n"
            "La descripción puede ser de hasta **4000** caracteres.\n"
            "Hay un límite conjunto de **6000** caracteres (incluyendo nuevas líneas) para los embeds.\n"
            "Ten en cuenta que la descripción se puede __separar en múltiples líneas__.",
            color=Admin.CONTRAST_COLOR,
        )

        emb.set_author(
            name="<< Icono de Autor | Nombre de Autor",
            url="http://example.com/orbyt",
            icon_url="https://i.imgur.com/KmwxpHF.png",
        )

        emb.set_footer(
            text="<< Icono de Pie del Embed | Este es el Pie del Embed",
            icon_url="https://i.imgur.com/V8xDSE5.png",
        )

        for i in range(1, 3):
            emb.add_field(
                name=f"Línea {i}",
                value=f"El texto de la línea {i}\nEs en la misma línea",
                inline=True,
            )

        emb.add_field(
            name="Línea 3",
            value="El texto de la línea 3\nNO es en la misma línea",
            inline=False,
        )

        emb.set_image(url="https://i.imgur.com/EhtHWap.png")
        emb.set_thumbnail(url="https://i.imgur.com/hq8nDF2.png")

        return emb

    @command()
    @has_guild_permissions(administrator=True)
    @default_permissions(administrator=True)
    async def embed(self, ctx: GuildContext, *, msg: str | None = None) -> Any:
        """Crea un embed personalizado"""

        if ctx.message.reference:
            message = ctx.message.reference.resolved

        else:
            if msg:
                try:
                    message = await MessageConverter().convert(ctx, msg)
                except (ChannelNotReadable, MessageNotFound):
                    return await ctx.reply(
                        "No se ha podido convertir el mensaje", ephemeral=True
                    )
            else:
                message = None

        if message:
            if len(message.embeds) > 0:  # type: ignore
                embed = discord.Embed.from_dict(message.embeds[0].to_dict())  # type: ignore
                def_embed = embed
            else:
                embed = discord.Embed()
                def_embed = self.generate_help_embed()
        else:
            def_embed = self.generate_help_embed()
            embed = discord.Embed()

        await ctx.reply(
            embed=def_embed, view=EmbedBuilderView(timeout=600, target=ctx, embed=embed)
        )

    # MODERATION COMMANDS

    @group(name="moderation")
    @default_permissions(moderate_members=True)
    @has_guild_permissions(moderate_members=True)
    async def mod_group(self, ctx: GuildContext) -> Any:
        """Comandos de moderación"""
        return await ctx.send_help(self.mod_group)

    @mod_group.group(name="nickname")
    @has_guild_permissions(manage_nicknames=True)
    async def mod_nickname(self, ctx: GuildContext) -> Any:
        """Gestiona los nicks de los usuarios"""
        return await ctx.send_help(self.mod_nickname)

    @mod_nickname.command(name="reset")
    @has_guild_permissions(manage_nicknames=True)
    @discord.app_commands.describe(member="El miembro al que reiniciar el nick")
    @commands.bot_has_permissions(manage_nicknames=True)
    async def mod_nick_reset(self, ctx: GuildContext, *, member: discord.Member) -> Any:
        """Reestablece el nick de un usuario"""
        await ctx.defer()

        if member.top_role > ctx.author.top_role:
            return await ctx.reply(
                "No puedes gestionar a un usuario con un rol mayor al tuyo.",
                ephemeral=True,
            )

        if member.guild_permissions > ctx.permissions:
            return await ctx.reply(
                "No puedes gestionar a un usuario con más permisos que tú.",
                ephemeral=True,
            )

        if member.top_role > ctx.me.top_role:
            return await ctx.reply(
                "No puedo gestionar a un usuario con un rol mayor al mío.",
                ephemeral=True,
            )

        await member.edit(nick=None)
        await ctx.reply(f"Se ha reiniciado el nick de {member.mention}")

    @mod_nickname.command(name="set")
    @has_guild_permissions(manage_nicknames=True)
    @discord.app_commands.describe(
        member="El miembro al que cambiar el nick", nick="El nuevo nick"
    )
    @commands.bot_has_permissions(manage_nicknames=True)
    async def mod_nick_set(
        self, ctx: GuildContext, member: discord.Member, *, nick: str
    ) -> Any:
        """Establece el nick de un usuario"""
        await ctx.defer()

        if member.top_role > ctx.author.top_role:
            return await ctx.reply(
                "No puedes gestionar a un usuario con un rol mayor al tuyo.",
                ephemeral=True,
            )

        if member.guild_permissions > ctx.permissions:
            return await ctx.reply(
                "No puedes gestionar a un usuario con más permisos que tú.",
                ephemeral=True,
            )

        if member.top_role > ctx.me.top_role:
            return await ctx.reply(
                "No puedo gestionar a un usuario con un rol mayor al mío.",
                ephemeral=True,
            )

        await member.edit(nick=nick[:32])
        await ctx.reply(f"Se ha establecido el nick de {member.mention} a `{nick}`")


async def setup(bot: Bot) -> Any:
    await bot.add_cog(Admin(bot))
