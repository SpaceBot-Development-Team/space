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

# pylint: disable=wrong-import-order

import datetime
import logging
import re
import asyncio
import discord
from discord.ext import (
    commands,
    tasks,
)

from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    List,
    Optional,
    Sequence,
    TypeVar,
    ParamSpec,
    NamedTuple,
)
from functools import partial as _partial

from _types import Bot, command, GuildContext, group
from _types.flags import RemoveVouchFlags
from _types import errors

from models import Guild, VouchsConfig, VouchGuildUser
from .utils.paginator import EmbedPaginator

if TYPE_CHECKING:
    from typing_extensions import Unpack

# pylint: enable=wrong-import-order
logger = logging.getLogger(__name__)
PartialData = ParamSpec("PartialData")
PartialResult = TypeVar("PartialResult")


def partial(
    func: Callable[PartialData, PartialResult],
    *args: PartialData.args,
    **kwargs: PartialData.kwargs,
) -> _partial[PartialResult]:
    """Returns a partially invoked function"""
    return _partial(func, *args, **kwargs)


class BulkDeleteResult(NamedTuple):
    """Named tuple that represents a bulk delete"""

    success: List[discord.abc.Snowflake]
    error: List[discord.abc.Snowflake]


F = TypeVar("F")
M = TypeVar("M")

Everyone = commands.parameter(
    default=lambda ctx: ctx.guild.default_role, displayed_default="<everyone>"
)

log = logging.getLogger(__name__)


def can_run_vouch():
    """Checks if a command can be run by vouch configs"""

    async def predicate(ctx: GuildContext) -> bool:
        if ctx.command.name.lower() == "help":
            return False  # Don't raise any error

        guild = await Guild.get_or_none(id=ctx.guild.id)

        if not guild or not guild.alter:
            ctx.command.reset_cooldown(ctx)
            raise errors.NoVouchConfig()

        vouchs = await VouchsConfig.get_or_none(id=ctx.guild.id)

        if not vouchs:
            ctx.command.reset_cooldown(ctx)
            raise errors.NoVouchConfig()

        if not vouchs.enabled:
            ctx.command.reset_cooldown(ctx)
            raise errors.VouchsDisabled()

        if not vouchs.command_like:
            ctx.command.reset_cooldown(ctx)
            raise errors.NoVouchCommand()

        if ctx.channel.id not in vouchs.whitelisted_channels:
            raise errors.NotAllowedVouchChannel(vouchs.whitelisted_channels)

        return True

    return commands.check(predicate)


class Vouchs(commands.Cog):
    """Comandos relacionados a vouchs"""

    TICK: ClassVar[str] = "<:tick:1216850806419095654>"
    LOADING: ClassVar[str] = "<a:loading:1224392749860786357>"
    utctime = partial(datetime.time, tzinfo=datetime.UTC)

    def __init__(self, bot: Bot) -> None:
        self.bot: Bot = bot
        self.vouch_pattern = re.compile(r"(?i)^.*?<@!?(\d+)>(.+)?$", re.MULTILINE)

    @tasks.loop(
        time=[
            utctime(hour=0, minute=0),
            utctime(hour=12, minute=0),
            utctime(hour=22, minute=0),
        ]
    )
    async def sanity_vouch_checks(self) -> Any:
        """Sanity check to remove unnecessary members"""

        log.info("Started sanity vouch check")

        for guild in self.bot.guilds:
            log.debug("Searching in guild %s", guild.name)
            gcfg = await Guild.get_or_none(id=guild.id)
            if not gcfg or not gcfg.alter:
                log.debug(
                    "Skipping %s because it doesn't have any config or alter role set up",
                    guild.name,
                )
                continue

            configs = await VouchGuildUser.filter(guild=guild.id).all()

            if not configs:
                log.debug("Skipping %s because it doesn't have any alters", guild.name)
                continue

            for member in guild.members:
                config = discord.utils.get(configs, user=member.id)
                if not config:
                    log.debug("Skipping %s | Didn't have a config", str(member))
                    continue

                if not member.get_role(gcfg.alter):
                    await config.delete()
                    log.debug(
                        "Deleted config for %s | Didn't have the alter role",
                        str(member),
                    )

            await asyncio.sleep(5)

    # pylint: disable=line-too-long
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-return-statements
    @commands.Cog.listener()
    async def on_message(
        self, message: discord.Message, *, skip_command_check: bool = False
    ) -> Any:
        """Event called when a message is recieved"""
        if not message.guild or message.author.bot:
            logger.debug(
                "Discarded vouchs message %s as no guild was found or was authorized by a bot",
                message.id,
            )
            return

        if not message.content:
            logger.debug(
                "Discarded vouchs message %s as no content was found", message.id
            )
            return

        if message.content.startswith(self.bot.user.mention):  # type: ignore
            content = message.content.removeprefix(self.bot.user.mention)  # type: ignore

        content = message.content.strip()

        if not await VouchsConfig.exists(id=message.guild.id):
            logger.debug(
                "Discarded vouchs message %s as no vouch config was found for guild %s",
                message.id,
                message.guild.id,
            )
            return

        cfg = await VouchsConfig.get_or_none(id=message.guild.id)

        if not cfg:
            logger.debug(
                "Discarded vouchs message %s as no config was strangly found",
                message.id,
            )
            return

        if not cfg.enabled:
            logger.debug(
                "Discarded vouchs message %s as vouchs were disabled", message.id
            )
            return

        if not skip_command_check:
            if cfg.command_like:
                logger.debug(
                    "Discarded vouchs message %s as vouchs were command like and not automatic",
                    message.id,
                )
                return

        if message.channel.id not in cfg.whitelisted_channels:
            logger.debug(
                "Discarded vouchs message %s as channel was not whitelisted", message.id
            )
            return

        matches: list[tuple[str, str]] = self.vouch_pattern.findall(
            content,
        )

        if len(matches) <= 0:
            return

        if cfg.multiplier:
            multiplier = cfg.multiplier
        else:
            multiplier = 1

        for user_raw_mention, reason in matches:
            user_id = int(user_raw_mention)

            if not reason or len(reason) <= 0:
                reason = "Legit"

            if user_id in message.raw_mentions:
                user_cfg = await VouchGuildUser.filter(
                    guild=message.guild.id
                ).get_or_none(user=user_id)

                if user_cfg is None:
                    user_cfg = await VouchGuildUser.create(
                        guild=message.guild.id, user=user_id
                    )

                vouchs = user_cfg.vouchs
                vouchs += 1 * multiplier
                user_cfg.vouchs = vouchs

                if not user_cfg.recent:
                    user_cfg.recent = [
                        f"{message.author.mention} ({message.author.id}) : {reason} : [Mensaje](<{message.jump_url}>)",
                    ]
                else:
                    if len(user_cfg.recent) > 10:
                        actual_recent = user_cfg.recent[:9]
                        actual_recent.append(
                            f"{message.author.mention} ({message.author.id}) : {reason} : [Mensaje](<{message.jump_url}>)"
                        )

                        user_cfg.recent = actual_recent

                    else:
                        user_cfg.recent.append(
                            f"{message.author.mention} ({message.author.id}) : {reason} : [Mensaje](<{message.jump_url}>)"
                        )

                await user_cfg.save()

        await message.add_reaction("✅")

    async def delete_messages_after(
        self, time: float, *messages: discord.PartialMessage
    ) -> BulkDeleteResult:
        """Deletes the messages after X time, returns the deleted message object."""

        await asyncio.sleep(time)

        error: List[discord.PartialMessage] = []
        deleted: List[discord.PartialMessage] = []

        for message in messages:
            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound):
                error.append(message)
            else:
                deleted.append(message)
            await asyncio.sleep(0.1)  # prevent ratelimits

        return BulkDeleteResult(deleted, error)  # type: ignore # Message is a abc.Snowflake protocol subclass

    @group(fallback="add")
    @commands.cooldown(1, 5, commands.BucketType.member)
    @can_run_vouch()
    async def vouch(
        self, ctx: GuildContext, alter: discord.Member, *, reason: str
    ) -> Any:
        """Añade un vouch a un miembro. Este debe de contener el rol configurado como alter.

        Parámetros
        ----------
        alter: Miembro
            El alter al que añadir el vouch
        reason: Texto
            La razón (o rewards) por las que dices que es legit.
        """
        if alter.bot:
            if ctx.interaction:
                await ctx.interaction.response.send_message(
                    "No se puede añadir vouch a un bot.", ephemeral=True
                )
            else:
                try:
                    await ctx.message.add_reaction("❌")
                except (discord.Forbidden, discord.HTTPException):
                    ret = await ctx.reply("No se puede añadir vouch a un bot.")
                    await self.bot.loop.create_task(
                        self.delete_messages_after(5.0, ret, ctx.message),
                        name="Delete Vouch Messages",
                    )
            return

        guild = await Guild.get_or_none(id=ctx.guild.id)

        if not guild:
            return await ctx.reply("Este servidor no tiene los vouchs configurados.")

        if not alter.get_role(guild.alter):
            if ctx.interaction:
                return await ctx.interaction.response.send_message(
                    "Este usuario no tiene el rol configurado como alter",
                    ephemeral=True,
                )
            return await ctx.message.add_reaction("❌")

        vouchs = await VouchGuildUser.get_or_none(guild=ctx.guild.id, user=alter.id)
        config = await VouchsConfig.get_or_none(id=ctx.guild.id)

        if not config:
            multiplier = 1
        else:
            multiplier = config.multiplier

        if not vouchs:
            vouchs = await VouchGuildUser.create(
                guild=ctx.guild.id, user=alter.id, vouchs=0, recent=[]
            )

        vouchs.vouchs += 1 * multiplier

        if not vouchs.recent:
            vouchs.recent = [
                f"{ctx.author.mention} ({ctx.author.id}) : {reason} : [Mensaje](<{ctx.message.jump_url}>)"
            ]

        else:
            if len(vouchs.recent) > 10:
                vouchs.recent = vouchs.recent[:9] + [
                    f"{ctx.author.mention} ({ctx.author.id}) : {reason} : [Mensaje](<{ctx.message.jump_url}>)"
                ]
            else:
                vouchs.recent.append(
                    f"{ctx.author.mention} ({ctx.author.id}) : {reason} : [Mensaje](<{ctx.message.jump_url}>)"
                )

        await vouchs.save()

        if ctx.interaction:
            await ctx.interaction.response.send_message(
                f"Se ha añadido {1*multiplier} vouch{'s' if 1*multiplier > 1 else ''} a {alter.mention}"
            )
        else:
            await ctx.message.add_reaction("✅")

    async def get_alter_role(self, ctx: GuildContext) -> Optional[int]:
        """Returns the alter role for the ctx guild, or ``None``"""
        config = await Guild.get_or_none(id=ctx.guild.id)
        if not config:
            return None
        return config.alter

    @vouch.command(name="remove")
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def vouch_remove(
        self, ctx: GuildContext, amount: int, *, flags: RemoveVouchFlags
    ) -> None:
        """Quita un vouch de un usuario.

        Parameters
        ----------
        amount: int
            La cantidad de vouchs que quitar.
        user: Union[discord.User, discord.Member]
            El alter al que quitar el vouch.
        remove_recent: bool
            Si se debería quitar tantos vouchs recientes como vouchs
            a quitar.
        """

        role = await self.get_alter_role(ctx)

        if not role or not flags.user.get_role(role):
            if ctx.interaction is not None:
                return await ctx.interaction.response.send_message(
                    "Este usuario no es alter", ephemeral=True
                )
            return await ctx.message.add_reaction("\N{CROSS MARK}")

        config = await VouchGuildUser.get_or_none(
            guild=ctx.guild.id, user=flags.user.id
        )

        if not config:
            if ctx.interaction is not None:
                return await ctx.interaction.response.send_message(
                    "Este alter no tiene vouchs", ephemeral=True
                )
            return await ctx.message.add_reaction("\N{CROSS MARK}")

        if amount > config.vouchs:
            await ctx.reply(
                f"No puedes quitar más vouchs a {flags.user.mention} de los que tiene.",
                allowed_mentions=discord.AllowedMentions.none(),
                ephemeral=True,
            )
            return

        config.vouchs -= amount

        if flags.remove_recent is True:
            if len(config.recent) < amount:
                config.recent = []
            else:
                config.recent = config.recent[amount:]

        await config.save()
        await ctx.reply(
            f"Se han quitado `{amount}` vouchs a {flags.user.mention}",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @staticmethod
    def _check(f: ModelDict, m: discord.Member) -> bool:
        return f.user == m.id

    def _get_mutual_items(
        self,
        first: Sequence[F],
        second: Sequence[M],
        *,
        key: Optional[Callable[[F, M], bool]] = None,
    ) -> Sequence[F]:
        if key is None:
            key = lambda f, m: f == m  # pylint: disable=unnecessary-lambda-assignment

        mutual_items = [f for f in first if any(key(f, m) for m in second)]
        self.bot.logger.debug("_get_mutual_items return %s", mutual_items)
        return mutual_items

    @command()
    @commands.cooldown(1, 60, commands.BucketType.guild)
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def vreset(
        self, ctx: GuildContext, *, entity: Optional[discord.Member] = None
    ) -> None:
        """Reinicia los vouchs de un usuario, un rol o todos.

        Parameters
        ----------
        entity: Optional[discord.Member]
            La entidad al que reiniciar los vouchs, dejar en blanco para resetear a @everyone
        """

        if entity is not None:
            config = await VouchGuildUser.get_or_none(
                user=entity.id, guild=ctx.guild.id
            )

            if not config:
                configs = []
            else:
                configs = [
                    config,
                ]
        else:
            configs = await VouchGuildUser.filter(guild=ctx.guild.id).all()

        if configs is None or len(configs) == 0:
            if ctx.interaction:
                return await ctx.interaction.response.send_message(
                    "No se pueden resetear los vouchs, por favor, comprueba que hay mínimo 1 usuario con mínimo 1 vouch en el servidor..",
                    ephemeral=True,
                )
            return await ctx.message.add_reaction("\N{CROSS MARK}")

        approximate_time = len(configs) + len(configs) * 0.5

        ret = await ctx.reply(
            f"{self.LOADING} | Reseteando los vouchs... Tiempo estimado: {approximate_time:.2f} segundos"
        )

        for config in configs:
            config.recent = []
            config.vouchs = 0
            await config.save()
            await asyncio.sleep(0.5)

        await ret.edit(content=f"{self.TICK} | Proceso terminado exitósamente")

    @command()
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def vouchs(  # pylint: disable=too-many-return-statements
        self, ctx: GuildContext, *, alter: discord.Member = commands.Author
    ) -> discord.Message | None:
        """Comprueba los vouchs de un alter.

        Parámetros
        ----------
        alter: Miembro
            El alter del que ver los vouchs, o tú.
        """
        if alter.bot:
            if ctx.interaction:
                await ctx.interaction.response.send_message(
                    "No se puede añadir vouch a un bot.", ephemeral=True
                )
            else:
                try:
                    await ctx.message.add_reaction("❌")
                except (discord.Forbidden, discord.HTTPException):
                    ret = await ctx.reply("No se puede añadir vouch a un bot.")
                    await self.bot.loop.create_task(
                        self.delete_messages_after(5.0, ret, ctx.message),
                        name="Delete Vouch Messages",
                    )
            return

        if alter.bot:
            return await ctx.reply(
                "No puedes ver la información de un bot", ephemeral=True
            )

        cfg = await VouchsConfig.get_or_none(id=ctx.guild.id)
        guild = await Guild.get_or_none(id=ctx.guild.id)

        if not cfg:
            return await ctx.reply(
                "No se puede ver estadísticas de vouchs al no estar configuradas",
                ephemeral=True,
            )

        if not cfg.enabled:
            return await ctx.reply(
                "Los vouchs no están habilitados en este servidor", ephemeral=True
            )

        if not guild:
            return await ctx.reply(
                "Este usuario no tiene el rol configurado como alter", ephemeral=True
            )

        if not alter.get_role(guild.alter):
            await cfg.delete()
            return await ctx.reply(
                "Este usuario no tiene el rol configurado como alter", ephemeral=True
            )

        user = await VouchGuildUser.get_or_none(guild=ctx.guild.id, user=alter.id)

        if not user:
            return await ctx.reply(
                "Este usuario no tiene vouchs disponibles", ephemeral=True
            )

        embed = discord.Embed(
            title="Tus vouchs" if alter.id == ctx.author.id else f"Vouchs de {alter}",
            description=f"Tiene un total de {user.vouchs or 0} vouchs",
            color=alter.color,
        )

        if user.recent and len(user.recent) > 0:
            for recent in user.recent:
                embed.add_field(name="\u2800", value=recent, inline=True)

        await ctx.reply(embed=embed)

    @command(aliases=["vlb"])
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def vleaderboard(
        self,
        ctx: GuildContext,
    ) -> None:
        """Mira una tabla con los que más vouchs tienen en el servidor"""

        paginator = EmbedPaginator(
            self.bot, commands.Paginator("", ""), owner=ctx.author, timeout=1700
        )

        async with ctx.typing():
            configs = (
                await VouchGuildUser.filter(guild=ctx.guild.id)
                .all()
                .order_by("-vouchs")
            )

            for cfg in configs:
                await paginator.add_line(f"<@{cfg.user}>: `{cfg.vouchs}` vouchs")

        await paginator.send_to(ctx)

    @command(aliases=["vrc"])
    @commands.cooldown(1, 60 * 60 * 6, commands.BucketType.guild)
    @discord.app_commands.checks.cooldown(1, 60 * 60 * 6, key=lambda i: (i.guild_id))
    @discord.app_commands.default_permissions(manage_guild=True)
    @commands.has_permissions(manage_guild=True)
    @commands.max_concurrency(1, commands.BucketType.guild, wait=False)
    async def vrecount(self, ctx: GuildContext, *, limit: int = 50) -> None:
        """Relee el canal de vouchs para añadir vouchs a los alters a los que no fue posible añadirles."""

        if limit > 150:
            await ctx.reply(
                "El límite de mensajes es de 150, introduzca un límite válido",
                ephemeral=True,
            )
            ctx.command.reset_cooldown(ctx)
            return
        if limit < 0:
            await ctx.reply(
                "El mínimo de mensajes es de 0, introduzca un límite válido",
                ephemeral=True,
            )
            ctx.command.reset_cooldown(ctx)
            return

        config = await VouchsConfig.get_or_none(id=ctx.guild.id)

        if not config:
            await ctx.reply("No están configurados los vouchs", ephemeral=True)
            ctx.command.reset_cooldown(ctx)
            return

        if not config.enabled:
            await ctx.reply("No se han habilitado los vouchs", ephemeral=True)
            ctx.command.reset_cooldown(ctx)
            return

        if not config.whitelisted_channels:
            await ctx.reply("No hay canales de vouchs", ephemeral=True)
            ctx.command.reset_cooldown(ctx)
            return

        eta = limit + len(config.whitelisted_channels) * 8

        bot_message = await ctx.reply(
            f"{self.LOADING} | Comenzando el proceso... Tiempo estimado: {eta} segundos"
        )

        for partial_id in config.whitelisted_channels:
            partial_msgable = self.bot.get_partial_messageable(
                partial_id, guild_id=ctx.guild.id
            )

            async for message in partial_msgable.history(limit=limit + 1):
                if message.author.bot or message.author.id == self.bot.user.id:  # type: ignore
                    continue

                reactions = message.reactions
                can_add_vouch = True

                for reaction in reactions:
                    async for reacted in reaction.users():
                        if reacted.id == self.bot.user.id:  # type: ignore
                            can_add_vouch = False
                            break

                if not can_add_vouch:
                    continue

                await self.on_message(message, skip_command_check=True)
                await asyncio.sleep(1)

            await asyncio.sleep(3)

        await bot_message.edit(content=f"{self.TICK} | Proceso terminado exitosamente")

    @command(aliases=["vmp"])
    @commands.has_guild_permissions(manage_guild=True)
    @discord.app_commands.default_permissions(manage_guild=True)
    @commands.cooldown(1, 60 * 60, commands.BucketType.guild)
    @discord.app_commands.checks.cooldown(1, 60 * 60, key=lambda i: i.guild_id)
    @discord.app_commands.describe(
        multiplier="Por cuanto hay que multiplicar la cantidad de vouchs. 1 por defecto."
    )
    async def vmultiplier(self, ctx: GuildContext, *, multiplier: int) -> None:
        """Añade un multiplicador de vouchs"""

        if multiplier < 1:
            await ctx.reply("No se puede aplicar un multiplicador menor que 1")
            return

        if not await VouchsConfig.exists(id=ctx.guild.id):
            await VouchsConfig.create(id=ctx.guild.id, multiplier=multiplier)
        else:
            config = await VouchsConfig.get(id=ctx.guild.id)
            config.multiplier = multiplier

        await ctx.reply(
            f"Se ha añadido un multiplicador de `{multiplier}` para los vouchs"
            if multiplier != 1
            else "Se ha reiniciado el multiplicador de vouchs"
        )


async def setup(bot: Bot) -> None:
    """Setup function to add the cog to the bot"""
    await bot.add_cog(Vouchs(bot))
