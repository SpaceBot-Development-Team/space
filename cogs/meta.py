from __future__ import annotations

from typing import Any, Mapping, Optional, TypeAlias, Union, TYPE_CHECKING, ClassVar

from discord.ext import commands, menus
import discord.ext.commands.view
from .utils.paginator import SpacePages
import discord
import inspect
import itertools
import bs4


if TYPE_CHECKING:
    from _types.bot import Bot

    RoboDanny: TypeAlias = Bot
    from _types.context import GuildContext

from _types.context import Context

RoboPages: TypeAlias = SpacePages


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
            signature = f"{command.qualified_name} {command.signature}"
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
        return f"{alias} {command.signature}"

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
        await menu.start()

    async def send_cog_help(self, cog):
        entries = await self.filter_commands(cog.get_commands(), sort=True)
        menu = HelpMenu(
            GroupHelpPageSource(cog, entries, prefix=self.context.clean_prefix),
            ctx=self.context,
        )
        await menu.start()

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
        await self.context.send(embed=embed)

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
        await menu.start()


class Meta(commands.Cog):
    EVAL_COMMAND_URL: ClassVar[str] = (
        "https://try.w3schools.com/try_python.php?x=0.2113021433279212"
    )
    LOADING: ClassVar[str] = "<a:loading:1224392749860786357>"

    """Comandos misceláneos"""

    def __init__(self, bot: Bot) -> None:
        bot.help_command = PaginatedHelpCommand()
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


class CodeModal(discord.ui.Modal):
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
