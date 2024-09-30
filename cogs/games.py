from __future__ import annotations
from typing import Any

import discord, asyncio
import discord.ext.commands as commands

from _types import Context, Bot, command
from sessions import games
from sessions.games import battleship, typerace


class Juegos(commands.Cog):
    """Comandos de juegos para que te diviertas ;)"""

    def __init__(self, bot: Bot) -> None:
        self.bot: Bot = bot

    @command(name="tictactoe", aliases=["j3", "join3", "ttt"])
    @commands.cooldown(1, 30, commands.BucketType.member)
    @discord.app_commands.describe(rival="El rival contra el que jugar")
    async def join3(self, ctx: Context, *, rival: discord.Member) -> Any:
        """Juega un 3 en raya contra alguien"""

        if rival.bot:
            ctx.command.reset_cooldown(ctx)
            return await ctx.reply(
                "¿Por qué querrías jugar contra un bot?", ephemeral=True, delete_after=5
            )

        check_message = await ctx.reply(
            f"{rival.mention}, {ctx.author.mention} quiere jugar al 3 en raya contigo. Reacciona con `✅` para aceptar."
        )
        await check_message.add_reaction("✅")

        def check(payload: discord.RawReactionActionEvent):
            if not payload.guild_id:
                return False
            if "add" not in payload.event_type.lower():
                return False

            return (
                (payload.message_id == check_message.id)
                and (payload.guild_id == ctx.guild.id)
                and (payload.user_id == rival.id)
                and (payload.member.id == rival.id)
                and (str(payload.emoji) == "✅")
            )

        try:
            await self.bot.wait_for("raw_reaction_add", check=check, timeout=60.0)
        except asyncio.TimeoutError:
            ctx.command.reset_cooldown(ctx)
            await check_message.clear_reaction("✅")
            return await check_message.edit(
                content="Se ha agotado el tiempo de espera, no se realizará el juego"
            )

        view = games.TicTacToe(ctx.author, rival)

        await check_message.clear_reaction("✅")
        await check_message.edit(
            content=f"Es el turno de {ctx.author.mention}", view=view
        )

        self.bot.add_view(view, message_id=check_message.id)

    @command(name="battleship", aliases=["bs"])
    @commands.cooldown(1, 30, commands.BucketType.member)
    @discord.app_commands.describe(rival="El rival contra el que jugar")
    async def battleship(self, ctx: Context, *, rival: discord.Member) -> Any:
        """Juega a un Hundir la Flota"""

        if rival.bot:
            return await ctx.reply(
                "¿Por qué querrías jugar contra un bot?", ephemeral=True, delete_after=5
            )

        if rival.id == ctx.author.id:
            return await ctx.reply(
                "Busca a alguien __más__ para jugar", ephemeral=True, delete_after=5
            )

        prompt = battleship.Prompt(ctx.author, rival)
        prompt.message = await ctx.send(
            f"{rival.mention} ha sido desafiado a un juego de Hundir la Flota con {ctx.author.mention}.\n"
            "Para aceptar, por favor pulsa el botón de abajo para prepararte.",
            view=prompt,
        )


async def setup(bot: Bot) -> None:
    await bot.add_cog(Juegos(bot))
