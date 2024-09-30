from __future__ import annotations

from typing import TYPE_CHECKING, Any, Coroutine, Generator, Literal
import discord
import asyncio
import copy
import time
import traceback

from jishaku.paginators import PaginatorEmbedInterface
from discord.ext.commands.cog import Cog
from discord.ext import commands
from _types import Context, Bot


if TYPE_CHECKING:
    from typing_extensions import Self


class PerfMocker:
    def __init__(self) -> None:
        self.loop = asyncio.get_running_loop()

    def permissions_for(self, obj: Any) -> discord.Permissions:
        perms = discord.Permissions.all()
        perms.administrator = False
        perms.embed_links = False
        perms.add_reactions = False
        return perms

    def __getattr__(self, attr: str) -> Self:
        return self

    def __call__(self, *args: Any, **kwargs: Any) -> Self:
        return self

    def __repr__(self) -> str:
        return "<PerfMocker>"

    def __await__(self) -> Generator[Any, None, Self]:
        future: asyncio.Future[Self] = self.loop.create_future()
        future.set_result(self)
        return future.__await__()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: Any) -> Self:
        return self

    def __len__(self) -> Literal[0]:
        return 0

    def __bool__(self) -> Literal[False]:
        return False


class Owner(Cog, command_attrs=dict(hidden=True)):
    def __init__(self, bot: Bot) -> None:
        self.bot: Bot = bot

    def cog_check(self, ctx: Context) -> Coroutine[Any, Any, bool]:
        return self.bot.is_owner(ctx.author)

    @commands.command(name="bot-servers", hidden=True)
    @commands.is_owner()
    async def _bot_servers(self, ctx: Context) -> None:
        base_paginator = commands.Paginator(
            None,
            None,
        )
        base_paginator.add_line(
            (
                f"**Cantidad de servidores:** {len(self.bot.guilds)}\n"
                "~~~~~~~~~~~~~~~~~~~~~~~~~~"
            )
        )

        for guild in self.bot.guilds:
            base_paginator.add_line(
                (
                    f"**Nombre:** {guild.name}\n"
                    f"**Dueño:** <@{guild.owner_id}> ({guild.owner_id})\n"
                    f"**Miembros:** {guild.member_count or guild.approximate_member_count}\n"
                    "--------------------"
                )
            )

        paginator = PaginatorEmbedInterface(
            bot=self.bot,
            paginator=base_paginator,
            owner=ctx.author,
            delete_message=True,
            embed=discord.Embed(color=self.bot.default_color),
        )
        await paginator.send_to(ctx.channel)

    @commands.command(hidden=True)
    async def perf(self, ctx: Context, *, command: str) -> None:
        """Calcula el rendimiento de un comando, intentando suprimir todas las peticiones HTTP y a la DB"""

        message: discord.Message = copy.copy(ctx.message)
        message.content = ctx.prefix + command

        new_ctx = await self.bot.get_context(message, cls=type(ctx))
        new_ctx._state = PerfMocker()  # type: ignore
        new_ctx.channel = PerfMocker()  # type: ignore

        if new_ctx.command is None:
            await ctx.reply("No command found")
            return

        start = time.perf_counter()
        try:
            await new_ctx.command.invoke(new_ctx)
        except commands.CommandError:
            end = time.perf_counter()
            success = False
            try:
                await ctx.reply(f"```py\n{traceback.format_exc()}\n```")
            except discord.HTTPException:
                pass
        else:
            end = time.perf_counter()
            success = True

        await ctx.reply(
            f"Status: {ctx.tick(success)} Tiempo de ejecución: {(end-start) * 1000:.2f}ms"
        )


async def setup(bot: Bot) -> None:
    await bot.add_cog(Owner(bot))
