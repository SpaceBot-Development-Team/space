"""Custom Bot and CommandTree"""

from __future__ import annotations
import logging
import os

# pylint: disable=protected-access
# pylint: disable=wrong-import-order

from attr import dataclass

from asyncio import iscoroutinefunction

import aiohttp
import datetime

import discord
from discord.ext.commands import Bot as BotBase
from discord.app_commands import CommandTree
from discord.app_commands.models import (
    AppCommand,
    AppCommandGroup,
    Argument as AppCommandArgument,
)
from discord import Emoji, PartialEmoji, app_commands as apps
from discord.ext.commands.errors import ExtensionAlreadyLoaded
from discord.ext import commands
from tortoise import Tortoise, connections

from .context import Context
from .errors import SuggestionFailure, VouchFailure
from .events import Dispatchable

from logging import Logger, INFO, getLogger


import sys
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    Generator,
    Iterable,
    List,
    NamedTuple,
    Optional,
    TypeVar,
    Union,
    cast,
)


CtxT = TypeVar("CtxT", bound="commands.Context")
logger = logging.getLogger(__name__)


# pylint: enable=wrong-import-order


async def prefix(bot: Bot, message: discord.Message) -> List[str]:
    """Returns the prefix for X message"""
    prefix = bot.guild_prefixes.get(message.guild.id, "!")  # type: ignore
    mentions = commands.when_mentioned(bot, message)
    return mentions + [prefix]


class ParameterLocalization(NamedTuple):
    """Named tuple to store the localizations of tree commands"""

    name_localization: dict[discord.Locale, str]
    description_localization: dict[discord.Locale, str]


class TreeCommand:
    """Represents a tree command, saved with the `~app_commands.Command` object
    and `~app_commands.AppCommand` metadata.
    """

    def __init__(
        self,
        *,
        synced: AppCommand | AppCommandGroup,
        decorated: discord.app_commands.Command | discord.app_commands.Group,
    ) -> None:
        self._discord_command: AppCommand | AppCommandGroup = synced
        self._dpy_command: discord.app_commands.Command | discord.app_commands.Group = (
            decorated
        )

    @discord.utils.cached_property
    def mention(self) -> str:
        """Returns a string allowing to mention this command"""
        if self.parent:
            return (
                f"</{self.parent.qualified_name} {self._dpy_command.name}"
                f":{self._discord_command.id}"  # type: ignore
            )
        return f"</{self._dpy_command.qualified_name}:{self._discord_command.id}>"  # type: ignore

    @discord.utils.cached_property
    def qualified_name(self) -> str:
        """Returns the full name (including parents)"""
        return self._dpy_command.qualified_name

    @discord.utils.cached_property
    def name(self) -> str:
        """Returns this command's name (without parent; also see
        :attr:`TreeCommand.qualified_name`)
        """
        return self._discord_command.name

    @discord.utils.cached_property
    def name_localizations(self) -> dict[discord.Locale, str]:
        """Returns the name localizations of this command"""
        return self._discord_command.name_localizations

    @discord.utils.cached_property
    def description(self) -> str:
        """Returns the description of this command"""
        return self._dpy_command.description

    @discord.utils.cached_property
    def description_localizations(self) -> dict[discord.Locale, str]:
        """Returns the description localizations of this command"""
        return self._discord_command.description_localizations

    @discord.utils.cached_property
    def parameters(self) -> list[AppCommandArgument]:
        """Returns the parameters of this command"""
        return [opt for opt in self.walk_arguments()]

    @discord.utils.cached_property
    def subcommands(self) -> list[AppCommandGroup]:
        """Returns the subcommands, if any"""
        return [sub for sub in self.walk_subcommands()]

    @discord.utils.cached_property
    def parameters_localizations(
        self,
    ) -> dict[AppCommandArgument, ParameterLocalization]:
        """Returns the parameter localizations"""
        return {
            opt: ParameterLocalization(
                opt.name_localizations, opt.description_localizations
            )
            for opt in self.walk_arguments()
        }

    @discord.utils.cached_property
    def parent(self) -> discord.app_commands.Group | None:
        """Returns this command's parent, or ``None``"""
        return self._dpy_command.parent

    @discord.utils.cached_property
    def root_parent(self) -> discord.app_commands.Group | None:
        """Returns this command's root parent (first parent), or ``None``"""
        return self._dpy_command.root_parent

    @discord.utils.cached_property
    def default_permissions(self) -> discord.Permissions:
        """:class:`Permissions`: The minimum permissions needed to run this command, this
        can be overridden per guild. Try using :attr:`TreeCommand.default_member_permissions`
        instead as it has more real information.
        """
        return self._dpy_command.default_permissions or discord.Permissions.none()

    @discord.utils.cached_property
    def default_member_permissions(self) -> discord.Permissions:
        """:class:`Permissions`: The Discord side member permissions needed for this command,
        overrides :attr:`TreeCommand.default_permissions`.
        """
        return getattr(
            self._discord_command,
            "default_member_permissions",
            self.default_permissions,
        )

    def walk_subcommands(self) -> Generator[AppCommandGroup, Any, None]:
        """Yields the subcommands, if any"""
        for option in self._discord_command.options:
            if option.type in (
                discord.AppCommandOptionType.subcommand,
                discord.AppCommandOptionType.subcommand_group,
            ):
                yield option  # type: ignore

    def walk_arguments(self) -> Generator[AppCommandArgument, Any, None]:
        """Yields the arguments (parameters) of this command"""
        for option in self._discord_command.options:
            if option.type not in (
                discord.AppCommandOptionType.subcommand,
                discord.AppCommandOptionType.subcommand_group,
            ):
                yield option  # type: ignore


# pylint: disable=line-too-long
class Tree(CommandTree):
    """🌳"""

    if TYPE_CHECKING:
        client: Bot  # type: ignore

    def __init__(self, client: Bot, *, fallback_to_global: bool = True) -> None:
        super().__init__(client, fallback_to_global=fallback_to_global)
        self.logger: Logger = getLogger("bot.tree")
        self.logger.setLevel(INFO)
        self._synced_guild_commands: dict[int, list[AppCommand]] = {}
        self._synced_commands: list[AppCommand] = []

    async def copy_and_sync(self, guild: discord.Object) -> list[AppCommand]:
        """Copies the global commands into a guild and automatically sync them"""
        self.copy_global_to(guild=guild)
        synced = await self.sync(guild=guild)
        self.logger.info(
            "Synced %s commands into guild with ID %s", len(synced), guild.id
        )

        return self._synced_guild_commands[guild.id]

    async def sync(self, *, guild: discord.abc.Snowflake = discord.utils.MISSING) -> list[AppCommand]:  # type: ignore
        if guild not in (discord.utils.MISSING, None):
            app_commands = await super().sync(guild=guild)
            to_append = []

            for app in app_commands:
                if app.type == discord.AppCommandType.chat_input:
                    to_append.append(app)

            self._synced_guild_commands[guild.id] = to_append

            del app_commands
            del to_append

            return self._synced_guild_commands[guild.id]

        self._synced_commands = await super().sync(guild=None)
        return self._synced_commands

    @property
    def commands(self) -> list[TreeCommand]:
        """list[:class:`TreeCommand`]: Returns all global commands"""
        return [command for command in self.walk_commands()]

    def get_guild_commands(
        self, guild: discord.abc.Snowflake = discord.utils.MISSING
    ) -> list[TreeCommand]:
        """Gets the commands of X guild"""
        return list(self.walk_commands(guild=guild))

    def walk_commands(self, *, guild: discord.abc.Snowflake = discord.utils.MISSING) -> Generator[TreeCommand, Any, None]:  # type: ignore  # pylint: disable=arguments-differ
        commands = (  # pylint: disable=redefined-outer-name
            self._synced_commands
            if guild in (discord.utils.MISSING, None)
            else self._synced_guild_commands[guild.id]
        )

        for command in commands:
            yield TreeCommand(synced=command, decorated=self.get_command(command.name, guild=guild if guild not in (discord.utils.MISSING, None) else None, type=discord.AppCommandType.chat_input))  # type: ignore

    async def on_error(
        self, itx: discord.Interaction, error: apps.AppCommandError, /
    ) -> None:
        """Error handler for app commands"""

        context = await self.client.get_context(itx)

        if isinstance(error, discord.app_commands.MissingPermissions):
            new_err = commands.MissingPermissions(
                error.missing_permissions, *error.args
            )
        elif isinstance(error, discord.app_commands.MissingAnyRole):
            new_err = commands.MissingAnyRole(error.missing_roles)
        elif isinstance(error, discord.app_commands.BotMissingPermissions):
            new_err = commands.BotMissingPermissions(
                error.missing_permissions, *error.args
            )
        elif isinstance(error, discord.app_commands.MissingPermissions):
            new_err = commands.MissingPermissions(
                error.missing_permissions, *error.args
            )
        elif isinstance(error, discord.app_commands.MissingRole):
            new_err = commands.MissingRole(error.missing_role)
        elif isinstance(error, discord.app_commands.CommandOnCooldown):
            if not context.command:
                cd = commands.Cooldown(error.cooldown.rate, error.cooldown.per)
            else:
                cd = context.command.cooldown
            new_err = commands.CommandOnCooldown(cd, error.retry_after, commands.BucketType.member)  # type: ignore
        elif isinstance(error, discord.app_commands.CheckFailure):
            new_err = commands.CheckFailure(*error.args)
        elif isinstance(error, discord.app_commands.NoPrivateMessage):
            new_err = commands.NoPrivateMessage(*error.args)
        else:
            new_err = commands.CommandError(*error.args)

        await self.client.on_command_error(context, new_err)  # type: ignore


# pylint: enable=line-too-long


@dataclass(repr=True, slots=True, kw_only=True)
class _Inners:
    """Dataclass that holds DB data"""

    db_url: str
    db_password: str


class Bot(BotBase):
    """🤖"""

    default_color: ClassVar[discord.Color] = discord.Color(0x5719C2)
    cog_emojis: Dict[str, Union[PartialEmoji, Emoji, str]] = {}

    @staticmethod
    def thanks_for_adding() -> discord.Embed:
        """Returns an embed to send when adding the bot"""
        return discord.Embed(
            title="¡Gracias por añadirme!",
            description="Para obtener ayuda puedes usar `!help`.\n"
            "Para cambiar el prefijo puedes usar `!setup` o `/setup bot`.\n"
            "Puedes cambiar la configuración de una manera más sencilla visitando "
            "[el panel de control](https://space-bot-web.onrender.com/)",
            color=discord.Color.blurple(),
        ).set_thumbnail(
            url="https://cdn.discordapp.com/avatars/1178306404323434576/a_92c2acc86861fc9b8526f103ef427417.gif?size=1024"  # pylint: disable=line-too-long
        )

    def __init__(self, *, db_url: str, db_password: str, **kwargs: Any) -> None:
        """The main bot class

        Parameters
        ----------
        models : str
            The models relative or absolute path
        db_url : str
            The database url
        db_password : str
            The database password
        """

        intents = discord.Intents()
        intents.voice_states = True
        intents.guild_messages = True
        intents.guilds = True
        intents.guild_polls = True
        intents.guild_reactions = True
        intents.members = True
        intents.message_content = True

        self.__tokens: dict[str, str] = kwargs.pop("tokens", {})
        self.initial_extensions: List[str] = kwargs.pop("initial_extensions", [])

        super().__init__(
            command_prefix=prefix,
            intents=intents,
            tree_cls=Tree,
            max_messages=None,
            allowed_mentions=discord.AllowedMentions.none(),
            status=discord.Status.idle,
            activity=discord.CustomActivity(
                "Viendo tus vouchs",
                emoji=discord.PartialEmoji.from_str(
                    "<a:ANTARTICO_FantasmaBits:1203639200679862363>"
                ),
            ),
            **kwargs,
        )
        del intents  # Save memory

        self._inners: _Inners = _Inners(db_url=db_url, db_password=db_password)
        self.logger: Logger = getLogger("bot.internals")
        self.ffmpeg_executable: str = (
            "ffmpeg" if sys.platform == "linux" else "D:\\FFmpeg\\bin\\ffmpeg.exe"
        )
        self.assured_guild_configs: bool = False
        self.session: aiohttp.ClientSession = discord.utils.MISSING
        self.denied_users: set[int] = set()

        self.logger.info(
            "\n".join(
                (
                    "Bot instated with following attributes:",
                    "Intents: %s" % dict(self.intents),
                    "ffmpeg executable dir: %s" % self.ffmpeg_executable,
                    "Initial extensions: %s" % self.initial_extensions,
                )
            )
        )
        self.guild_prefixes: dict[int, str] = {}

    def set_session(self, session: aiohttp.ClientSession) -> None:
        """Sets the new client session"""
        self.session = session

        self.logger.debug("New client session: %s", repr(session))

    def get_token(self, api: str) -> str | None:
        """Gets the API token for certain API, if available"""

        self.logger.debug("Requested token for %s", api)
        return self.__tokens.get(api.lower(), None)

    async def setup_hook(self) -> None:
        await Tortoise.init(
            modules={"models": ["models"]},
            db_url="asyncpg://" + self._inners.db_url.format(self._inners.db_password),
        )
        await Tortoise.generate_schemas(safe=True)
        await self.load_extensions(self.initial_extensions)
        await self.load_extension("jishaku")
        await self._load_opted_out_users()
        await self._load_guild_prefixes()
        self._populate_cogs_display_emojis()
        self._add_dispatchables()

    async def _load_guild_prefixes(self) -> None:
        from models import Guild  # type: ignore

        for config in await Guild.all():
            self.guild_prefixes[config.id] = config.prefix
        logger.debug("Loaded all guild prefixes")

    def update_guild_prefix(self, guild_id: int, prefix: str, /) -> None:
        """Updates a cached guild prefix"""
        self.guild_prefixes[guild_id] = prefix

    def _add_dispatchables(self) -> None:
        for cog in self.cogs.values():
            for attr in dir(cog):
                if attr in dir(commands.Cog):
                    continue
                v: Any = getattr(cog, attr, None)
                if not isinstance(v, Dispatchable):
                    continue

                if v.name in self.extra_events:
                    self.extra_events[v.name].append(v)
                else:
                    self.extra_events[v.name] = [v]

    async def maybe_coro(self, function: Callable[..., Any], *args, **kwargs) -> Any:
        """Executes the function and returns its future, if function is not a coro
        then it is executed in another executor, if it is ran by this method, no kwargs
        are allowed."""

        if iscoroutinefunction(function):
            return await function(*args, **kwargs)

        return await self.loop.run_in_executor(None, function, *args)

    async def close(self) -> None:
        return await super().close()

    async def load_extensions(self, iterable: Iterable[str], /) -> None:
        """Loads multiple extensions"""
        for ext in iterable:
            try:
                await self.load_extension(ext)
            except ExtensionAlreadyLoaded:
                self.logger.warning(
                    "Extension %s is already loaded. Ignoring", repr(ext)
                )
                continue

    async def load_extension(self, name: str, *, package: Optional[str] = None) -> None:
        self.logger.debug(
            "Loaded extension %s with package %s", repr(name), repr(package)
        )
        await super().load_extension(name, package=package)

    def _wrap_locale_strs(self) -> None:
        for command in self.tree.get_commands():
            try:
                command._convert_to_locale_strings()  # type: ignore
            except AttributeError:
                continue

        self.logger.debug("Converted commands to locale string")

    @discord.utils.cached_property
    async def team_members(self) -> list[discord.TeamMember] | None:
        """Fetches all the team members and returns it.

        Returns
        -------
        list[discord.TeamMember] | None
            The team members.
        """

        info = await self.application_info()

        if info.team:
            return info.team.members
        return None

    async def on_message(self, message: discord.Message, /) -> None:
        if message.author.bot or message.author == self.user:
            return

        context = await self.get_context(message, cls=Context)

        if not context.valid:
            return

        if context.author.id in self.denied_users:
            await context.reply(
                (
                    "¡Has negado que el bot utilice tus mensajes "
                    "para la ejecución de comandos de prefijo!"
                    f" PUedes volver a permitirlo usando `{context.clean_prefix}opt-in`."
                )
            )
            return

        await context.command.invoke(context)  # type: ignore

    async def process_commands(self, message: discord.Message, /) -> Any:
        if message.author.id in self.denied_users:
            await message.author.send(
                (
                    "¡Has negado que el bot utilice tus mensajes "
                    "para la ejecución de comandos de prefijo!"
                    f" PUedes volver a permitirlo usando `{await self.get_prefix(message)}opt-in`."
                )
            )
            return
        await super().process_commands(message)

    # pylint: disable=line-too-long
    # pylint: disable=too-many-branches
    async def on_command_error(self, ctx: Context["Bot"], error: commands.CommandError, /) -> Any:  # type: ignore
        """Error handler for commands"""

        ctx.command = cast(commands.Command, ctx.command)

        if isinstance(error, commands.CommandNotFound):
            cmd = ctx.invoked_with or ctx.command.qualified_name
            await ctx.reply(
                f"❌ | No existe ningún comando llamado `{cmd}`.",
                delete_after=5,
                ephemeral=True,
            )
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(
                f'⌛ | Estás en congelamiento, vuélvelo a intentar {discord.utils.format_dt((datetime.datetime.now() + datetime.timedelta(seconds=error.retry_after)), style="R")}',
                ephemeral=True,
            )
        elif isinstance(error, commands.MissingPermissions):
            await ctx.reply(
                f'❔ | No tienes suficientes permisos para poder ejecutar este comando.\nNeceistas: ```yaml\n{", ".join(error.missing_permissions)}```',
                ephemeral=True,
            )
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.reply(
                f'❔ | El bot no tiene suficientes permisos para poder ejectuar este comando.\nNecesita de: ```yaml\n{", ".join(error.missing_permissions)}```',
                ephemeral=True,
            )
        elif isinstance(error, commands.MissingAnyRole):
            await ctx.reply(
                f'❔ | Requieres de alguno de estos roles para poder ejecutar el comando: {", ".join([("<@&" + str(role) + ">") for role in error.missing_roles])}',
                allowed_mentions=discord.AllowedMentions.none(),
                ephemeral=True,
            )
        elif isinstance(error, commands.MissingRole):
            await ctx.reply(
                f"❔ | Requires del siguiente rol para poder ejecutar el comando: <@&{error.missing_role}>",
                allowed_mentions=discord.AllowedMentions.none(),
                ephemeral=True,
            )
        elif isinstance(error, commands.BotMissingAnyRole):
            await ctx.reply(
                f'❔ | El bot necesita de uno de los siguientes roles: {", ".join(("<@&" + str(role) + ">") for role in error.missing_roles)}',
                allowed_mentions=discord.AllowedMentions.none(),
                ephemeral=True,
            )
        elif isinstance(error, commands.BotMissingRole):
            await ctx.reply(
                f"❔ | El bot requiere del siguiente rol para poder ejecutar el comando: <@&{error.missing_role}>",
                allowed_mentions=discord.AllowedMentions.none(),
                ephemeral=True,
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(
                f"❌ | Te ha faltado el argumento `{error.param.name}`\nEjemplo de uso: ```yaml\n{ctx.command.qualified_name} {ctx.command.signature}```",
                ephemeral=True,
            )
        elif isinstance(error, commands.MissingFlagArgument):
            await ctx.reply(
                f"❌ | Te ha faltado proporcionar el valor de `{error.flag.name}`.",
                ephemeral=True,
            )
        elif isinstance(error, commands.ArgumentParsingError):
            await ctx.reply(
                f"❓ | Uno de los valores proporcionados al comando no se han podido convertir, asegúrate de usarlo correctamente.\nEjemplo de uso: ```yaml\n{ctx.command.qualified_name} {ctx.command.signature}```",
                ephemeral=True,
            )
        elif isinstance(error, commands.BadBoolArgument):
            await ctx.reply(
                f"❌ | `{error.argument}` no es un valor válido para ``True`` o ``False``.",
                ephemeral=True,
            )
        elif isinstance(error, commands.BadColorArgument):
            await ctx.reply(
                f"❌ | `{error.argument}` no es un valor válido de un color.",
                ephemeral=True,
            )
        elif isinstance(error, commands.BadLiteralArgument):
            await ctx.reply(
                f"❌ | `{error.argument}` no es un valor válido de las opciones disponibles.",
                ephemeral=True,
            )
        elif isinstance(error, commands.BadInviteArgument):
            await ctx.reply(
                f"❌ | `{error.argument}` no es una invitación válida (está expirada o no existe).",
                ephemeral=True,
            )
        elif isinstance(error, commands.BadUnionArgument):
            await ctx.reply(
                f'❌ | `{error.param.name}` ha sufrido varios errores de conversión con el valor que proporcionaste, se probaron: {", ".join([conv.__class__.__name__ for conv in error.converters])}, y todos fallaron.',
                ephemeral=True,
            )
        elif isinstance(error, commands.BadFlagArgument):
            await ctx.reply(
                f"❌ | El parámetro `{error.flag.name}` no pudo convertir `{error.argument}` a `{error.flag.annotation.__class__.__name__}`.",
                ephemeral=True,
            )
        elif isinstance(error, commands.MaxConcurrencyReached):
            await ctx.reply(
                f"❌ | Se ha alcanzado el límite de ejecuciones simultáneas de este comando ({error.number} uso(s) {self._get_bucket_name(error.per)}).",
                ephemeral=True,
            )
        elif isinstance(error, VouchFailure):
            await ctx.reply(
                f"❌ | {error}",
                ephemeral=True,
            )
        elif isinstance(error, SuggestionFailure):
            await ctx.reply(
                f"❌ | {error}",
                ephemeral=True,
            )
        else:
            await ctx.reply(
                f"❓ | Un error desconocido ha ocurrido.\nRéportalo en el servidor de soporte: ```py\n{error}```.",
                ephemeral=True,
            )

    # pylint: enable=line-too-long
    # pyling: enable=too-many-branches

    async def _load_opted_out_users(self) -> None:
        from models import User

        try:
            users = await User.filter(optedIn=False).all()
            for user in users:
                self.denied_users.add(user.id)

            self.logger.debug("Loaded opted out users")
        except:
            self.logger.warning("Failed to load opted out users")

    def get_message(
        self, id: int, /
    ) -> Optional[discord.Message]:  # pylint: disable=redefined-builtin
        """Gets a message and returns it"""
        return self._connection._get_message(id)

    # pylint: disable=too-many-return-statements
    def _get_bucket_name(self, bucket: commands.BucketType) -> str:
        if bucket == commands.BucketType.category:
            return "por categoría"
        if bucket == commands.BucketType.channel:
            return "por canal"
        if bucket == commands.BucketType.guild:
            return "por servidor"
        if bucket == commands.BucketType.member:
            return "por miembro"
        if bucket == commands.BucketType.role:
            return "por rol"
        if bucket == commands.BucketType.user:
            return "por usuario"
        return "globalmente"

    # pylint: enable=too-many-return-statements

    def _populate_cogs_display_emojis(self) -> None:
        for cog_name, cog in self.cogs.items():
            emoji = self.cog_emojis.get(cog_name)
            if not emoji:
                continue

            if isinstance(emoji, str):
                emoji = PartialEmoji.from_str(emoji)
            if isinstance(emoji, Emoji):
                emoji = emoji._to_partial()

            setattr(cog, "display_emoji", emoji)

        self.logger.debug("Populated cogs display emojis")

    def _repopulate_cog_display_emojis(self) -> None:
        for cog_name, cog in self.cogs.items():
            if hasattr(cog, "display_emoji") or isinstance(
                getattr(cog, "display_emoji", None), PartialEmoji
            ):
                continue

            emoji = self.cog_emojis.get(cog_name)
            if not emoji:
                continue

            if isinstance(emoji, str):
                emoji = PartialEmoji.from_str(emoji)
            if isinstance(emoji, Emoji):
                emoji = emoji._to_partial()

            setattr(cog, "display_emoji", emoji)

        self.logger.debug("Repopulated cogs display emojis")

    async def reload_extension(
        self, name: str, *, package: Optional[str] = None
    ) -> None:
        await super().reload_extension(name, package=package)
        self._repopulate_cog_display_emojis()

        self.logger.debug(
            "Reloaded extension %s with package %s", repr(name), repr(package)
        )
