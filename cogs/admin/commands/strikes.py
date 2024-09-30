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

import datetime
import difflib
from typing import TYPE_CHECKING, Any, List, Optional, cast

import discord
from discord import app_commands
from discord.ext import commands

from _types import group
from _types.commandutil import can_run_strike
from models import Guild, StrikeGuildStaff

if TYPE_CHECKING:
    from _types import Bot, GuildContext


async def strike_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice]:
    """Strike autocomplete that returns all the available strikes"""

    user = interaction.namespace["user"]

    if user is None:  # If user not set yet
        return [
            app_commands.Choice(
                name="Escoge al staff que sancionar antes de que strike quitar",
                value="none",
            )
        ]

    config = await StrikeGuildStaff.get_or_none(
        user=user.id, guild=interaction.guild_id
    )

    if not config or not config.strikes:
        return [app_commands.Choice(name="Este staff no tiene strikes", value="none")]

    choices: List[app_commands.Choice] = []

    for creation, payload in config.strikes.items():
        name = creation + " | " + payload.get("reason")

        if current not in name:
            continue
        choices.append(
            app_commands.Choice(
                name=name[:100],
                value=creation,
            )
        )
    return choices


class SelectStrikeDropDown(discord.ui.Select):
    def __init__(self, matches: List[Any], cfg: StrikeGuildStaff) -> None:
        self.cfg: StrikeGuildStaff = cfg

        options: list[discord.SelectOption] = []
        for match in matches:
            timestamp, reason = str(match).split(" | ", maxsplit=1)

            options.append(
                discord.SelectOption(
                    label=match,
                    value=timestamp,
                    description=reason,
                )
            )

        super().__init__(
            placeholder="Seleccione el strike...",
            min_values=1,
            max_values=1,
            options=options,
            disabled=False,
            row=0,
        )

    async def callback(self, itx: discord.Interaction) -> Any:  # type: ignore | pylint: disable=arguments-renamed
        strike = self.values[0]
        strike = strike.strip()

        data = self.cfg.strikes.pop(strike)

        self.cfg.total_strikes -= data.get("amount")

        await self.cfg.save()

        description = "Se ha quitado el strike de <@{user}> del {strike_timestamp}:\nAutor: <@{executor_id}>\nRazón: {reason}\nStrikes: {amount}"
        description.format(
            user=self.cfg.user,
            strike_timestamp=discord.utils.format_dt(
                datetime.datetime.fromisoformat(strike), style="d"
            ),
            executor_id=data.get("executor_id"),
            reason=data.get("reason"),
            amount=data.get("amount"),
        )

        await itx.response.edit_message(
            view=None,
            content=None,
            embed=discord.Embed(
                color=itx.client.default_color, description=description  # type: ignore
            ),
        )


class ThisIsNotForYou(discord.app_commands.CheckFailure):
    def __init__(self) -> None:
        super().__init__()


class SelectStrike(discord.ui.View):
    def __init__(
        self, author: discord.abc.User, cfg: StrikeGuildStaff, matches: list[Any]
    ) -> None:
        self.author: discord.abc.User = author
        self.cfg: StrikeGuildStaff = cfg
        self.matches: list[Any] = matches

        super().__init__()

        self.add_item(SelectStrikeDropDown(matches, cfg))

    async def interaction_check(self, itx: discord.Interaction) -> bool:
        if not itx.user.id == self.author.id:
            raise ThisIsNotForYou()
        return True

    async def on_error(
        self,
        itx: discord.Interaction,
        error: Exception,
        item: discord.ui.Item["SelectStrike"],
    ) -> Any:
        if isinstance(error, ThisIsNotForYou):
            return await itx.response.send_message(
                "No puedes interactuar con este mensaje ya que no es tuyo",
                ephemeral=True,
            )


class StrikeAddFlags(commands.FlagConverter, prefix="--", delimiter=" "):
    reason: str = commands.flag(
        positional=True, description="La razón por la que añades el strike"
    )
    note: Optional[str] = commands.flag(
        default=None, description="La nota que añadir como pie de embed"
    )


class StrikesCommands:
    """Strikes commands"""

    def __init__(self, bot: Bot) -> None:
        self.bot: Bot = bot

    @group(
        name="strike",
        fallback="staff",
        usage="<staff> <strikes> <reason> [--note=None]",
    )
    @can_run_strike()
    @commands.has_permissions(moderate_members=True)
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(
        staff="El staff al que sancionar",
        strikes="La cantidad de strikes que añadir",
    )
    async def strike(
        self,
        ctx: GuildContext,
        staff: discord.Member,
        strikes: Optional[int] = 1,
        *,
        flags: StrikeAddFlags,
    ):
        """Añade un strike al staff proporcionado. Ha de tener permisos de moderar miembros."""
        if strikes is None:
            strikes = 1

        if not staff.guild_permissions.moderate_members:
            return await ctx.reply(
                "No puedes añadir strikes a este usuario por no ser considerado staff por parte de Discord",
                ephemeral=True,
                delete_after=5,
            )

        if staff.top_role >= ctx.author.top_role:
            return await ctx.reply(
                "No puedes añadir strikes a este staff por tener un rol superior o igual al tuyo",
                ephemeral=True,
                delete_after=5,
            )

        guild = await Guild.get_or_none(id=ctx.guild.id)

        if not guild or not guild.staff_report:
            return await ctx.reply(
                "No se han configurado los strikes",
                ephemeral=True,
                delete_after=5,
            )

        partial = self.bot.get_partial_messageable(
            guild.staff_report,
            guild_id=ctx.guild.id,
        )
        user_config, _ = await StrikeGuildStaff.get_or_create(
            {"total_strikes": 0, "strikes": {}},
            guild=ctx.guild.id,
            user=staff.id,
        )

        if user_config.strikes is None:
            user_config.strikes = {}

        if user_config.total_strikes is None:
            user_config.total_strikes = 0

        user_config.strikes.update(
            {
                datetime.datetime.now(datetime.timezone.utc).isoformat(): {
                    "executor_id": ctx.author.id,
                    "reason": flags.reason,
                    "amount": strikes,
                },
            },
        )
        user_config.total_strikes += strikes

        embed = discord.Embed(
            description=f"**{ctx.author.mention} ha sancionado a {staff.mention}**\n"
            "**Strikes:** {strikes}\n**Razón:** {flags.reason}",
            colour=discord.Colour.blurple(),
        )
        embed.set_author(
            name=ctx.author,
            icon_url=ctx.author.display_avatar.url,
        )

        if flags.note is not None:
            embed.set_footer(text=f"Nota: {flags.note[:2042]}")

        files = None

        if not ctx.interaction:
            if ctx.message.attachments:
                embed.description += "\n\n*Se adjuntaron imágenes*"  # type: ignore

                files = [
                    await attachment.to_file() for attachment in ctx.message.attachments
                ]
            await ctx.message.delete()
        else:
            await ctx.reply(
                "Se ha añadido tu strike",
                ephemeral=True,
            )

        await user_config.save()
        await partial.send(
            embed=embed,
            files=files,  # type: ignore
        )

    @strike.command(
        name="remove",
    )
    @can_run_strike()
    @commands.has_permissions(manage_guild=True)
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.autocomplete(
        strike=strike_autocomplete,
    )
    @app_commands.describe(
        staff="El staff al que quitar el strike",
        strike="El strike que quitar",
    )
    async def strike_remove(
        self,
        ctx: GuildContext,
        staff: discord.Member,
        *,
        strike: Optional[str] = None,
    ):
        """Quita un strike de un staff."""

        if ctx.interaction is not None:
            if strike:
                if strike.lower() == "none":
                    return await ctx.reply(
                        "Este staff no tiene strikes, aún...",
                        ephemeral=True,
                    )
                cfg = await StrikeGuildStaff.get_or_none(
                    user=staff.id, guild=ctx.guild.id
                )

                if not cfg:
                    return await ctx.reply(
                        "Este staff no tiene strikes, aún...",
                        ephemeral=True,
                    )

                data = cfg.strikes.pop(strike)
                cfg.total_strikes -= data.get("amount")

                await cfg.save()

                embed_description = (
                    f"Se ha quitado el strike de {staff.mention} del {discord.utils.format_dt(datetime.datetime.fromisoformat(strike), style='d')}:"
                    f"\nAutor: <@{data.get('executor_id')}>\nRazón: {data.get('reason')}\nStrikes: {data.get('amount')}"
                )

                return await ctx.reply(
                    embed=discord.Embed(
                        color=self.bot.default_color,
                        description=embed_description.format(
                            staff_mention=staff.mention,
                        ),
                    )
                )

        cfg = await StrikeGuildStaff.get_or_none(user=staff.id, guild=ctx.guild.id)

        if not cfg or not cfg.strikes or len(cfg.strikes.keys()) <= 0:
            return await ctx.reply(
                "Este staff no tiene strikes, aún...", delete_after=5, ephemeral=True
            )

        if not staff.guild_permissions.moderate_members:
            return await ctx.reply(
                "Este usuario no es considerado staff por Discord",
                ephemeral=True,
                delete_after=5,
            )

        choices = [
            created + " | " + pd.get("reason") for created, pd in cfg.strikes.items()
        ]

        if strike is not None:
            matches = difflib.get_close_matches(strike, choices, n=25, cutoff=0.2)
        else:
            matches = choices[:25]

        await ctx.reply(
            "Por favor, seleccione el strike que más se parece al indicado",
            view=SelectStrike(ctx.author, cfg, matches),
        )

    @strike.command(name="view")
    @app_commands.describe(
        staff="El staff del que ver los strikes",
    )
    @can_run_strike()
    @app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def strike_view(
        self,
        ctx: GuildContext,
        *,
        staff: discord.Member = commands.Author,
    ):
        """Comprueba los strikes del staff proporcionado, o tuyos."""

        if not staff.guild_permissions.moderate_members:
            string = "Este usuario no es considerado staff por Discord"
            return await ctx.reply(
                string,
                ephemeral=True,
            )  # type: ignore

        cfg = await StrikeGuildStaff.get_or_none(user=staff.id, guild=ctx.guild.id)
        strikes = cast(dict[str, dict[str, str | int]], cfg.strikes if cfg else {})

        if not cfg or not strikes or len(strikes.keys()) <= 0:
            return await ctx.reply(
                (
                    "Este usuario no tiene strikes, aún..."
                    if staff.id != ctx.author.id
                    else "No tienes strikes, aún..."
                ),
                ephemeral=True,
            )

        embed = discord.Embed(color=self.bot.default_color)

        embed.title = (
            "Tus strikes" if staff.id == ctx.author.id else f"Strikes de {staff}"
        )
        embed.description = f"Tiene un total de `{cfg.total_strikes}` strikes"

        for created_at, data in strikes.items():
            created_at_dt = datetime.datetime.fromisoformat(created_at)

            embed.add_field(
                name="Motivo: " + str(data.get("reason", "Incumplimiento de normas")),
                value=(
                    f'**Fecha del strike:** {discord.utils.format_dt(created_at_dt, style="d")} '
                    f'({discord.utils.format_dt(created_at_dt, style="R")})\n'
                    f'**Autor del strike:** <@{data.get("executor_id")}> (`{data.get("executor_id")}`)\n'
                    f'**Cantidad de strikes: {data.get("amount")}**'
                ),
            )

        await ctx.reply(embed=embed)
