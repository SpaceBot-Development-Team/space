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
import inspect
import itertools
import logging
from typing import Any, Mapping, Optional, TypeAlias, Union, TYPE_CHECKING, ClassVar

import bs4
import pygit2
import discord
import discord.ext.commands.view
from discord.ext import commands, menus
from discord.ext.commands.view import StringView

from _types.context import Context
from _types import command
from .utils.paginator import SpacePages

if TYPE_CHECKING:
    from _types.bot import Bot

    RoboDanny: TypeAlias = Bot
    from _types.context import GuildContext

RoboPages: TypeAlias = SpacePages
logger = logging.getLogger(__name__)


class Prefix(commands.Converter):
    async def convert(self, ctx: GuildContext, argument: str) -> str:
        user_id = ctx.bot.user.id

        if argument.startswith((f"<@{user_id}>", f"<@!{user_id}>")):
            raise commands.BadArgument(
                "Este es un prefijo reservado que se utiliza por defecto."
            )
        if len(argument) > 150:
            raise commands.BadArgument("Ese prefijo es muy largo.")
        return argument


class GroupHelpPageSource(menus.ListPageSource):
    def __init__(
        self,
        group: Union[commands.Group, commands.Cog],
        entries: list[commands.HybridCommand],
        *,
        prefix: str,
    ) -> None:
        super().__init__(entries=entries, per_page=6)

        self.group: Union[commands.Group, commands.Cog] = group
        self.prefix: str = prefix
        self.title: str = f"Comandos en `{self.group.qualified_name}`"
        self.description: str = self.group.description

    async def format_page(
        self, menu: SpacePages, commands: list[commands.HybridCommand]
    ) -> discord.Embed:
        embed = discord.Embed(
            title=self.title,
            description=self.description,
            colour=discord.Colour(0xA8B9CD),
        )

        for command in commands:
            signature = f"{PaginatedHelpCommand.get_usage_emojis(command)} {command.qualified_name} {command.signature}"
            embed.add_field(
                name=signature,
                value=command.short_doc or "Sin ayuda corta",
                inline=False,
            )

        maximum = self.get_max_pages()

        if maximum > 1:
            embed.set_author(
                name=f"Pág. {menu.current_page + 1}/{maximum} ({len(self.entries)} comandos)"
            )

        embed.set_footer(
            text=f'Usa "{self.prefix}help <comando>" para más información de uno.'
        )
        return embed


class HelpSelectMenu(discord.ui.Select["HelpMenu"]):
    def __init__(
        self, entries: dict[commands.Cog, list[commands.HybridCommand]], bot: RoboDanny
    ):
        super().__init__(
            placeholder="Selecciona una categoría...",
            min_values=1,
            max_values=1,
            row=0,
        )
        self.commands: dict[commands.Cog, list[commands.HybridCommand]] = entries
        self.bot: Bot = bot
        self.__fill_options()

    def __fill_options(self) -> None:
        self.add_option(
            label="Índice",
            emoji="👋",
            value="__index",
            description="La página de ayuda mostrando como usar el bot",
        )
        for cog, commands in self.commands.items():
            if not commands:
                continue
            description = cog.description.split("\n", 1)[0] or None
            emoji = getattr(cog, "display_emoji", None)
            self.add_option(
                label=cog.qualified_name,
                value=cog.qualified_name,
                description=description,
                emoji=emoji,
            )

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        value = self.values[0]
        if value == "__index":
            await self.view.rebind(FrontPageSource(), interaction)
        else:
            cog = self.bot.get_cog(value)
            if cog is None:
                await interaction.response.send_message(
                    "Los astros decidieron que esta categoría no exista", ephemeral=True
                )
                return

            commands = self.commands[cog]
            if not commands:
                await interaction.response.send_message(
                    "Esta categoría no tiene comandos que puedas utilizar",
                    ephemeral=True,
                )
                return

            source = GroupHelpPageSource(
                cog, commands, prefix=self.view.ctx.clean_prefix
            )
            await self.view.rebind(source, interaction)


class FrontPageSource(menus.PageSource):
    def is_paginating(self) -> bool:
        # This forces the buttons to appear even in the front page
        return True

    def get_max_pages(self) -> Optional[int]:
        # There's only one actual page in the front page
        # However we need at least 2 to show all the buttons
        return 2

    async def get_page(self, page_number: int) -> Any:
        # The front page is a dummy
        self.index = page_number
        return self

    def format_page(self, menu: HelpMenu, page: Any):
        embed = discord.Embed(title="Ayuda del Bot", colour=discord.Colour(0xA8B9CD))
        embed.description = inspect.cleandoc(
            f"""
            ¡Hola! Bienvenido a la página de ayuda

            Usa "{menu.ctx.clean_prefix}help comando" para más información de un comando.
            Usa "{menu.ctx.clean_prefix}help categoría" para más información de una categoría
            Usa el selector de abajo para elegir una categoría.
        """
        )

        embed.add_field(
            name="Servidor de Soporte",
            value="Para obtener más ayuda, únete al servidor de soporte oficial con https://discord.gg/m9UsWuaYDT",
            inline=False,
        )

        created_at = discord.utils.format_dt(menu.ctx.bot.user.created_at, "F")
        if self.index == 0:
            embed.add_field(
                name="¿Quién eres?",
                value=(
                    "Soy un bot creado por `@developeranonymous.`. ¡Soy un bot multiusos para servidores de recompensas! Llevo activo desde "
                    f"{created_at}. Tengo funciones como vouchs, juegos, y más. Puedes obtener "
                    "más información de mis comandos con el selector de abajo."
                ),
                inline=False,
            )
        elif self.index == 1:
            entries = (
                (
                    "Los emojis de los comandos",
                    "Si el comando contiene el emoji <:prefixed_command:1293248180606996600>, entonces se puede utilizar como "
                    f"comando prefijado (`{menu.ctx.prefix}comando`), si el comando contiene el emoji <:application_command:1293248219266027591> "
                    "entonces se puede utilizar como comando de aplicación (`/comando`).",
                ),
                (
                    "<argumento>",
                    "Esto significa que el argumento es __**obligatorio**__.",
                ),
                ("[argumento]", "Esto significa que el argumento es __**opcional**__."),
                (
                    "[A|B]",
                    "Esto significa que el argumento puede ser __**cualquiera de A o B**__.",
                ),
                (
                    "[argumento...]",
                    "Esto quiere decir que tiene mútliples argumentos.\n"
                    "Ahora que sabes lo básico... Deberías saber que...\n"
                    "__**¡No se escriben ni los corchetes, `|`s ni las `<>`!**__",
                ),
            )

            embed.add_field(
                name="¿Cómo uso este bot?",
                value="Leer el uso de un comando es muy sencillo.",
            )

            for name, value in entries:
                embed.add_field(name=name, value=value, inline=False)

        return embed


class HelpMenu(RoboPages):
    def __init__(self, source: menus.PageSource, ctx: Context):
        super().__init__(source, ctx=ctx, compact=True)

    def add_categories(
        self, commands: dict[commands.Cog, list[commands.HybridCommand]]
    ) -> None:
        self.clear_items()
        self.add_item(HelpSelectMenu(commands, self.ctx.bot))
        self.fill_items()

    async def rebind(
        self, source: menus.PageSource, interaction: discord.Interaction
    ) -> None:
        self.source = source
        self.current_page = 0

        await self.source._prepare_once()
        page = await self.source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(0)
        await interaction.response.edit_message(**kwargs, view=self)


class PaginatedHelpCommand(commands.HelpCommand):
    context: Context

    def __init__(self):
        super().__init__(
            command_attrs={
                "cooldown": commands.CooldownMapping.from_cooldown(
                    1, 3.0, commands.BucketType.member
                ),
                "help": "Muestra ayuda de un comando, grupo o categoría",
            }
        )

    async def on_help_command_error(self, ctx: Context, error: commands.CommandError):
        if isinstance(error, commands.CommandInvokeError):
            # Ignore missing permission errors
            if (
                isinstance(error.original, discord.HTTPException)
                and error.original.code == 50013
            ):
                return

            await ctx.send(str(error.original))

    def get_command_signature(self, command: commands.HybridCommand) -> str:
        parent = command.full_parent_name
        if len(command.aliases) > 0:
            aliases = "|".join(command.aliases)
            fmt = f"[{command.name}|{aliases}]"
            if parent:
                fmt = f"{parent} {fmt}"
            alias = fmt
        else:
            alias = command.name if not parent else f"{parent} {command.name}"
        return f"{self.get_usage_emojis(command)} {alias} {command.signature}"

    async def send_bot_help(self, mapping: Mapping):
        bot = self.context.bot

        def key(command: commands.HybridCommand) -> str:
            cog = command.cog
            return cog.qualified_name if cog else "\U0010ffff"

        entries: list[commands.HybridCommand] = await self.filter_commands(
            bot.commands, sort=True, key=key
        )

        all_commands: dict[commands.Cog, list[commands.HybridCommand]] = {}
        for name, children in itertools.groupby(entries, key=key):
            if name == "\U0010ffff":
                continue

            cog = bot.get_cog(name)
            assert cog is not None
            all_commands[cog] = sorted(children, key=lambda c: c.qualified_name)

        menu = HelpMenu(FrontPageSource(), ctx=self.context)
        menu.add_categories(all_commands)
        await menu.start(content=None)

    async def send_cog_help(self, cog):
        entries = await self.filter_commands(cog.get_commands(), sort=True)
        menu = HelpMenu(
            GroupHelpPageSource(cog, entries, prefix=self.context.clean_prefix),
            ctx=self.context,
        )
        await menu.start(content=None)

    @staticmethod
    def get_usage_emojis(
        command: commands.HybridCommand | commands.HybridGroup
    ) -> str:
        application_emoji = "<:application_command:1295442981129682945>"
        string = "<:prefixed_command:1295442979502428351>"
        if not isinstance(command, commands.HybridCommand):
            match type(command):
                case commands.Command:
                    return string
                case discord.app_commands.Command:
                    return application_emoji
                case (commands.HelpCommand, commands.DefaultHelpCommand, commands.MinimalHelpCommand):
                    return string + application_emoji
        if command.with_app_command and command.app_command:
            string += application_emoji
        return string

    def common_command_formatting(
        self,
        embed_like: discord.Embed,
        command: Union[commands.HybridCommand, commands.HybridGroup],
    ):
        embed_like.title = self.get_command_signature(command)
        if command.description:
            embed_like.description = f"{command.description}\n\n{command.help}"
        else:
            embed_like.description = command.help or "Sin ayuda corta"

    async def send_command_help(
        self, command: Union[commands.HybridCommand, commands.HybridGroup]
    ):
        # No pagination necessary for a single command.
        embed = discord.Embed(colour=discord.Colour(0xA8B9CD))
        self.common_command_formatting(embed, command)
        await self.context.send(content=None, embed=embed)

    async def send_group_help(self, group: commands.HybridGroup):
        subcommands = group.commands
        if len(subcommands) == 0:
            return await self.send_command_help(group)

        entries = await self.filter_commands(subcommands, sort=True)
        if len(entries) == 0:
            return await self.send_command_help(group)

        source = GroupHelpPageSource(group, entries, prefix=self.context.clean_prefix)
        self.common_command_formatting(source, group)
        menu = HelpMenu(source, ctx=self.context)
        await menu.start(content=None)


class Meta(commands.Cog):
    EVAL_COMMAND_URL: ClassVar[str] = (
        "https://try.w3schools.com/try_python.php?x=0.2113021433279212"
    )
    LOADING: ClassVar[str] = "<a:loading:1224392749860786357>"

    """Comandos misceláneos"""

    def __init__(self, bot: Bot) -> None:
        self.paginated_help_command = PaginatedHelpCommand()
        bot.help_command = self.paginated_help_command
        bot.help_command.cog = self

        self.bot = bot
        self._bot_help_cmd = self.bot.get_command("help")

    @staticmethod
    def blocking_get_from_html(html: str) -> bs4.Tag:
        bs = bs4.BeautifulSoup(html, "html")
        return bs.pre  # type: ignore

    async def get_from_html(self, html: str) -> bs4.Tag:
        return await self.bot.loop.run_in_executor(
            None, self.blocking_get_from_html, html
        )

    async def get_context(self, interaction: discord.Interaction) -> Context:
        bot = self.bot
        command = interaction.command
        if command is None:
            raise ValueError("interaction does not have command data")
        data = interaction.data
        if interaction.message is None:
            synthetic = {
                "id": interaction.id,
                "reactions": [],
                "embeds": [],
                "mention_everyone": False,
                "tts": False,
                "pinned": False,
                "edited_timestamp": None,
                "type": (
                    discord.MessageType.chat_input_command
                    if data.get("type", 1) == 1
                    else discord.MessageType.context_menu_command
                ),
                "flags": 64,
                "content": "",
                "mentions": [],
                "mention_roles": [],
                "attachments": [],
            }
            if interaction.channel_id is None:
                raise RuntimeError(
                    "interaction channel ID is null, this is probably a Discord bug"
                )
            channel = interaction.channel or discord.PartialMessageable(
                state=interaction._state,
                guild_id=interaction.guild_id,
                id=interaction.channel_id,
            )
            message = discord.Message(
                state=interaction._state, channel=channel, data=synthetic
            )
            message.author = interaction.user
            message.attachments = [
                a for _, a in interaction.namespace if isinstance(a, discord.Attachment)
            ]
        else:
            message = interaction.message
        prefix = "/" if data.get("type", 1) == 1 else "\u200b"
        ctx = Context(
            message=message,
            bot=bot,
            view=StringView(""),
            args=[],
            kwargs={},
            prefix=prefix,
            interaction=interaction,
            invoked_with=command.name,
            command=command,
        )
        interaction._baton = ctx
        ctx.command_failed = interaction.command_failed
        return ctx

    @discord.app_commands.command(name="help")
    @discord.app_commands.checks.cooldown(1, 30, key=lambda i: (i.guild_id, i.user.id))
    async def slash_help(
        self, interaction: discord.Interaction, *, command: str | None = None
    ) -> Any:
        """Muestra ayuda de un comando, grupo o categoría."""
        context = await self.bot.get_context(interaction)
        self.paginated_help_command.context = context
        await self.paginated_help_command.command_callback(context, command=command)

    @commands.command(name="evaluate", aliases=["eval"])
    @commands.cooldown(1, 60, commands.BucketType.member)
    async def prefix_evaluate(self, ctx: Context, *, code: str) -> None:
        """Evalúa código de Python."""

        original = await ctx.reply(f"{self.LOADING} | Evaluando código...")

        if code.startswith("```"):
            if not code.endswith("```"):
                await ctx.reply(
                    "¡Has proporcionado un bloque de código pero no lo has cerrado!"
                )
                ctx.command.reset_cooldown(ctx)
                return

            code = code.removeprefix("```")
            code = code.removesuffix("```")

            if code[:2] == "py":
                code = code[2:]

        async with self.bot.session.post(
            self.EVAL_COMMAND_URL, data={"code": code}
        ) as response:
            html = await response.text()
            result = await self.get_from_html(html)

            content = "```py\n" + result.get_text(strip=True) + "\n```"

        await original.edit(
            content=None,
            embed=discord.Embed(
                color=self.bot.default_color, description=content[:4096]
            ),
        )

    @discord.app_commands.command(name="evaluate")
    @discord.app_commands.allowed_installs(guilds=True, users=True)
    @discord.app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @discord.app_commands.checks.cooldown(1, 60, key=lambda i: (i.guild_id, i.user.id))
    async def slash_evaluate(
        self,
        itx: discord.Interaction,
    ) -> None:
        """Evalúa código de Python"""

        await itx.response.send_modal(
            CodeModal(self.bot, itx.user.id, itx.guild_id or 0)
        )

    @staticmethod
    def format_relative(dt: datetime.datetime) -> str:
        return discord.utils.format_dt(dt, "R")

    def format_commit(self, commit: pygit2.Commit) -> str:
        short, _, _ = commit.message.partition("\n")
        short_sha2 = commit.short_id
        commit_tz = datetime.timezone(
            datetime.timedelta(minutes=commit.commit_time_offset)
        )
        commit_time = datetime.datetime.fromtimestamp(commit.commit_time).astimezone(
            commit_tz
        )
        offset = self.format_relative(commit_time.astimezone(datetime.timezone.utc))
        return f"[`{short_sha2}`](https://github.com/SpaceBot-Development-Team/space/commit/{commit.id}) {short} ({offset})"

    async def get_latest_commits(self, count: int = 3) -> str:
        repo = pygit2.Repository(".git")
        commits = list(itertools.islice(repo.walk(repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL), count))  # type: ignore
        return "\n".join(self.format_commit(commit) for commit in commits)

    @command(name="stats")
    @commands.cooldown(1, 15, commands.BucketType.member)
    @discord.app_commands.allowed_installs(guilds=True, users=True)
    @discord.app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def command_bot_stats(self, ctx: Context) -> Any:
        """Comprueba las estadísticas del bot."""
        await ctx.defer()
        try:
            revision = await self.get_latest_commits()
        except Exception:
            revision = "*Ninguno... de momento*"
        embed = discord.Embed(description="Cambios más recientes:\n" + revision)
        embed.title = "Invitación al Servidor de Soporte Oficial"
        embed.url = "https://discord.gg/m9UsWuaYDT"
        embed.colour = self.bot.default_color

        total_members = 0
        total_unique = len(self.bot.users)

        text = 0
        voice = 0
        guilds = 0
        for guild in self.bot.guilds:
            guilds += 1
            if guild.unavailable:
                continue

            total_members += guild.member_count or guild.approximate_member_count or 0
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel):
                    text += 1
                elif isinstance(channel, discord.VoiceChannel):
                    voice += 1

        embed.add_field(
            name="Miembros", value=f"{total_members} en total\n{total_unique} únicos"
        )
        embed.add_field(
            name="Canales",
            value=f"{text+voice} en total\n{text} canales de texto\n{voice} canales de voz",
        )

        version = discord.__version__
        embed.add_field(name="Servidores", value=guilds)
        embed.set_footer(
            text=f"Hecho en discord.py v{version} con 💖 por @dev_anony",
            icon_url="http://i.imgur.com/5BFecvA.png",
        )
        embed.timestamp = discord.utils.utcnow()
        await ctx.reply(embed=embed)


class CodeModal(discord.ui.Modal):
    """Modal for app_commands evaluate command"""

    def __init__(self, bot: Bot, user_id: int, guild_id: int) -> None:
        self.bot: Bot = bot
        super().__init__(
            title="Evaluar Código",
            timeout=None,
            custom_id=f"code-evaluation:{user_id}:{guild_id}",
        )

    code = discord.ui.TextInput(
        label="Código", style=discord.TextStyle.long, max_length=4000, row=0
    )

    async def on_submit(self, itx: discord.Interaction) -> None:
        await itx.response.defer(thinking=True)
        async with self.bot.session.post(
            Meta.EVAL_COMMAND_URL, data={"code": self.code.value}
        ) as response:
            html = await response.text()
            result = await self.bot.loop.run_in_executor(
                None, Meta.blocking_get_from_html, html
            )

            content = "```py\n" + result.get_text(strip=True) + "\n```"

        await itx.followup.send(
            embed=discord.Embed(
                color=self.bot.default_color, description=content[:4096]
            )
        )


async def setup(bot: Bot) -> None:
    await bot.add_cog(Meta(bot))
