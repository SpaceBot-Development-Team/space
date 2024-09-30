"""Custom context"""

from __future__ import annotations

from typing import (
    Any,
    Iterable,
    List,
    Callable,
    TYPE_CHECKING,
    Optional,
    Tuple,
    TypeVar,
    Union,
    Generic,
)

import discord, io
from discord.ext import commands

from aiohttp import ClientSession

MISSING = discord.utils.MISSING

if TYPE_CHECKING:
    from .bot import Bot
    from models import SuggestionsConfig

T = TypeVar("T")


class ConfirmationView(discord.ui.View):
    def __init__(self, *, timeout: float, author_id: int, delete_after: bool) -> None:
        super().__init__(timeout=timeout)
        self.value: Optional[bool] = None
        self.delete_after: bool = delete_after
        self.author_id: int = author_id
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.author_id:
            return True
        else:
            await interaction.response.send_message(
                "Esta confirmación no te pertenece", ephemeral=True
            )
            return False

    async def on_timeout(self) -> None:
        if self.delete_after and self.message:
            await self.message.delete()

    @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.green)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.value = True
        await interaction.response.defer()
        if self.delete_after:
            await interaction.delete_original_response()

        self.stop()

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.defer()
        if self.delete_after:
            await interaction.delete_original_response()

        self.stop()


class DisambiguatorView(discord.ui.View, Generic[T]):
    message: discord.Message
    selected: T

    def __init__(self, ctx: Context, data: list[T], entry: Callable[[T], Any]):
        super().__init__()
        self.ctx: Context = ctx
        self.data: list[T] = data

        options = []
        for i, x in enumerate(data):
            opt = entry(x)
            if not isinstance(opt, discord.SelectOption):
                opt = discord.SelectOption(label=str(opt))
            opt.value = str(i)
            options.append(opt)

        select = discord.ui.Select(options=options)

        select.callback = self.on_select_submit
        self.select = select
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "Este selector no es para tí, perdón.", ephemeral=True
            )
            return False
        return True

    async def on_select_submit(self, interaction: discord.Interaction):
        index = int(self.select.values[0])
        self.selected = self.data[index]
        await interaction.response.defer()
        if not self.message.flags.ephemeral:
            await self.message.delete()

        self.stop()


class _CTX(commands.Context[Any]):
    author: discord.Member
    guild: discord.Guild
    channel: Union[discord.VoiceChannel, discord.TextChannel, discord.Thread]
    me: discord.Member
    prefix: str
    bot: Bot
    command: commands.Command
    prefix: str


class Context(_CTX):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def entry_to_code(self, entries: Iterable[Tuple[str, str]]) -> None:
        width = max(len(a) for a, b in entries)
        output = ["```"]

        for name, entry in entries:
            output.append(f"{name:<{width}}: {entry}")
        output.append("```")

        await self.send("\n".join(output))

    async def indented_entry_to_code(self, entries: Iterable[Tuple[str, str]]) -> None:
        width = max(len(a) for a, b in entries)
        output = ["```"]

        for name, entry in entries:
            output.append(f"\u200b{name:>{width}}: {entry}")
        output.append("```")
        await self.send("\n".join(output))

    def __repr__(self) -> str:
        # we need this for our cache key strat
        return "<Context>"

    async def translate(
        self,
        string: str,
        *,
        locale: discord.Locale = discord.utils.MISSING,
        data: Any = discord.utils.MISSING,
    ) -> str:
        """Translates a string and returns its resolved str"""

        if locale is discord.utils.MISSING:
            locale = discord.Locale.spain_spanish

        if self.interaction:
            ret = await self.interaction.translate(string, locale=locale, data=data)
        else:
            context = discord.app_commands.TranslationContext(
                discord.app_commands.TranslationContextLocation.other, data=data
            )
            translator = self.bot.tree.translator
            if not translator:
                ret = string
            else:
                ret = await translator.translate(
                    discord.app_commands.locale_str(string),
                    locale=locale,
                    context=context,
                )
        ret = ret or string

        if ret == "...":
            ret = string
        return ret

    async def send(
        self, content: Optional[str] = discord.utils.MISSING, **kwargs: Any
    ) -> discord.Message:
        if content is not None:
            if self.interaction is not None:
                locale = self.interaction.locale
            else:
                locale = discord.utils.MISSING
            content = await self.translate(content, locale=locale)
        return await super().send(content, **kwargs)

    @property
    def session(self) -> ClientSession:
        return self.bot.session

    @discord.utils.cached_property
    def replied_reference(self) -> Optional[discord.MessageReference]:
        ref = self.message.reference

        if ref and isinstance(ref.resolved, discord.Message):
            return ref.resolved.to_reference()
        return None

    @discord.utils.cached_property
    def replied_message(self) -> Optional[discord.Message]:
        ref = self.message.reference

        if ref and isinstance(ref.resolved, discord.Message):
            return ref.resolved
        return None

    async def disambiguate(
        self, matches: List[T], entry: Callable[[T], Any], *, ephemeral: bool = True
    ) -> T:
        if len(matches) == 0:
            raise ValueError("No se encontraron resultados.")

        if len(matches) == 1:
            return matches[0]

        if len(matches) > 25:
            raise ValueError("Demasiados resultados...")

        view = DisambiguatorView(self, matches, entry)
        view.message = await self.send(
            "Hay demasiadas coincidencias, ¿A cuál se refería?",
            view=view,
            ephemeral=ephemeral,
        )
        await view.wait()
        return view.selected

    async def prompt(
        self,
        message: str,
        *,
        timeout: float = 60.0,
        delete_after: bool = True,
        author_id: Optional[int] = None,
    ) -> Optional[bool]:
        """An interactive reaction confirmation dialog.

        Parameters
        -----------
        message: str
            The message to show along with the prompt.
        timeout: float
            How long to wait before returning.
        delete_after: bool
            Whether to delete the confirmation message after we're done.
        author_id: Optional[int]
            The member who should respond to the prompt. Defaults to the author of the
            Context's message.

        Returns
        --------
        Optional[bool]
            ``True`` if explicit confirm,
            ``False`` if explicit deny,
            ``None`` if deny due to timeout
        """

        author_id = author_id or self.author.id
        view = ConfirmationView(
            timeout=timeout, delete_after=delete_after, author_id=author_id
        )
        view.message = await self.send(message, view=view, ephemeral=delete_after)

        await view.wait()
        return view.value

    def tick(self, opt: Optional[bool], label: Optional[str] = None) -> str:
        lookup = {
            True: "<:tick:1216850806419095654>",
            False: "<:cross:1216850808587554937>",
            None: "<:null:1216850810982502613>",
        }
        emoji = lookup.get(opt, "<:cross:1216850808587554937>")

        if label is not None:
            return f"{emoji}: {label}"
        return emoji

    async def show_help(self, command: Any = None) -> None:
        """Shows the help command for the specified command if given.

        If no command is given, then it'll show help for the current
        command.
        """
        cmd = self.bot.get_command("help")
        command = command or self.command.qualified_name
        await self.invoke(cmd, command=command)  # type: ignore

    async def safe_send(
        self, content: str, *, escape_mentions: bool = True, **kwargs
    ) -> discord.Message:
        """Same as send except with some safe guards.

        1) If the message is too long then it sends a file with the results instead.
        2) If ``escape_mentions`` is ``True`` then it escapes mentions.
        """
        if escape_mentions:
            content = discord.utils.escape_mentions(content)

        if len(content) > 2000:
            fp = io.BytesIO(content.encode())
            kwargs.pop("file", None)
            return await self.send(
                file=discord.File(fp, filename="message_too_long.txt"), **kwargs
            )
        else:
            return await self.send(content)

    @property
    def locale(self) -> discord.Locale:
        """:class:`Locale`: Returns the main locale of this context."""
        if not self.interaction:
            return discord.Locale.spain_spanish
        return self.interaction.locale


class GuildContext(Context): ...


class SuggestionsContext(Context):
    config: SuggestionsConfig
