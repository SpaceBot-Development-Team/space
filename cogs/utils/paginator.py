from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional, Union
import discord
import traceback
from discord.ext import commands
from discord.ext.commands import Paginator as CommandPaginator
from discord.ext import menus

if TYPE_CHECKING:
    from ..._types.context import Context
    from ..._types.bot import Bot


class NumberedPageModal(discord.ui.Modal, title="Ir a la Página"):
    page = discord.ui.TextInput(
        label="Página", placeholder="Introduce un número", min_length=1
    )

    def __init__(self, max_pages: Optional[int]) -> None:
        super().__init__()

        if max_pages is not None:
            string = str(max_pages)

            self.page.placeholder = f"Introduce un número entre 1 y {string}"
            self.page.max_length = len(string)

    async def on_submit(self, itx: discord.Interaction) -> None:
        self.interaction = itx
        self.stop()


class SpacePages(discord.ui.View):
    def __init__(
        self,
        source: menus.PageSource,
        *,
        ctx: Context,
        check_embeds: bool = True,
        compact: bool = False,
    ) -> None:
        super().__init__()

        self.source: menus.PageSource = source
        self.check_embeds: bool = check_embeds
        self.ctx: Context = ctx
        self.message: Optional[discord.Message] = None
        self.current_page: int = 0
        self.compact: bool = compact

        self.clear_items()
        self.fill_items()

    def fill_items(self) -> None:
        if not self.compact:
            self.numbered_page.row = 1
            self.stop_pages.row = 1

        if self.source.is_paginating():
            max_pages = self.source.get_max_pages()
            use_last_and_first = max_pages is not None and max_pages >= 2

            if use_last_and_first:
                self.add_item(self.go_to_first_page)
            self.add_item(self.go_to_previous_page)
            if not self.compact:
                self.add_item(self.go_to_current_page)
            self.add_item(self.go_to_next_page)
            if use_last_and_first:
                self.add_item(self.go_to_last_page)
            self.add_item(self.stop_pages)

    async def _get_kwargs_from_page(self, page: int) -> Dict[str, Any]:
        value: discord.Embed = await discord.utils.maybe_coroutine(
            self.source.format_page, self, page
        )

        if isinstance(value, dict):
            return value
        elif isinstance(value, str):
            return {"content": value}
        elif isinstance(value, discord.Embed):
            return {"embeds": [value]}
        else:
            return value

    async def show_page(self, itx: discord.Interaction, page_no: int) -> None:
        page = await self.source.get_page(page_no)
        self.current_page = page_no
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(page_no)

        if kwargs:
            if itx.response.is_done():
                if self.message:
                    await self.message.edit(**kwargs, view=self)
            else:
                await itx.response.edit_message(**kwargs, view=self)

    def _update_labels(self, page_number: int) -> None:
        self.go_to_first_page.disabled = page_number == 0
        if self.compact:
            max_pages = self.source.get_max_pages()
            self.go_to_last_page.disabled = (
                max_pages is None or (page_number + 1) >= max_pages
            )
            self.go_to_next_page.disabled = (
                max_pages is not None and (page_number + 1) >= max_pages
            )
            self.go_to_previous_page.disabled = page_number == 0
            return

        self.go_to_current_page.label = str(page_number + 1)
        self.go_to_previous_page.label = str(page_number)
        self.go_to_next_page.label = str(page_number + 2)
        self.go_to_next_page.disabled = False
        self.go_to_previous_page.disabled = False
        self.go_to_first_page.disabled = False

        max_pages = self.source.get_max_pages()
        if max_pages is not None:
            self.go_to_last_page.disabled = (page_number + 1) >= max_pages
            if (page_number + 1) >= max_pages:
                self.go_to_next_page.disabled = True
                self.go_to_next_page.label = "…"
            if page_number == 0:
                self.go_to_previous_page.disabled = True
                self.go_to_previous_page.label = "…"

    async def show_checked_page(
        self, interaction: discord.Interaction, page_number: int
    ) -> None:
        max_pages = self.source.get_max_pages()
        try:
            if max_pages is None:
                # If it doesn't give maximum pages, it cannot be checked
                await self.show_page(interaction, page_number)
            elif max_pages > page_number >= 0:
                await self.show_page(interaction, page_number)
        except IndexError:
            # An error happened that can be handled, so ignore it.
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id in (
            self.ctx.bot.owner_id,
            self.ctx.author.id,
        ):
            return True
        await interaction.response.send_message(
            "¡Este menú no puede ser controlado por tí!", ephemeral=True
        )
        return False

    async def on_timeout(self) -> None:
        if self.message:
            await self.message.edit(view=None)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(
                "Un error desconocido ha ocurrido, disculpas.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Un error desconocido ha ocurrido, disculpas.", ephemeral=True
            )

    async def start(
        self, *, content: Optional[str] = None, ephemeral: bool = False
    ) -> None:
        if self.check_embeds and not self.ctx.channel.permissions_for(self.ctx.me).embed_links:  # type: ignore
            await self.ctx.send(
                "El bot no tiene permiso de adjuntar enlaces en este canal.",
                ephemeral=True,
            )
            return

        await self.source._prepare_once()
        page = await self.source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        if content:
            kwargs.setdefault("content", content)

        self._update_labels(0)
        self.message = await self.ctx.send(**kwargs, view=self, ephemeral=ephemeral)

    @discord.ui.button(label="≪", style=discord.ButtonStyle.grey)
    async def go_to_first_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """go to the first page"""
        await self.show_page(interaction, 0)

    @discord.ui.button(label="Atrás", style=discord.ButtonStyle.blurple)
    async def go_to_previous_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """go to the previous page"""
        await self.show_checked_page(interaction, self.current_page - 1)

    @discord.ui.button(label="Actual", style=discord.ButtonStyle.grey, disabled=True)
    async def go_to_current_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        pass

    @discord.ui.button(label="Siguiente", style=discord.ButtonStyle.blurple)
    async def go_to_next_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """go to the next page"""
        await self.show_checked_page(interaction, self.current_page + 1)

    @discord.ui.button(label="≫", style=discord.ButtonStyle.grey)
    async def go_to_last_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """go to the last page"""
        # The call here is safe because it's guarded by skip_if
        await self.show_page(interaction, self.source.get_max_pages() - 1)  # type: ignore

    @discord.ui.button(label="Ir a página...", style=discord.ButtonStyle.grey)
    async def numbered_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """lets you type a page number to go to"""
        if self.message is None:
            return

        modal = NumberedPageModal(self.source.get_max_pages())
        await interaction.response.send_modal(modal)
        timed_out = await modal.wait()

        if timed_out:
            await interaction.followup.send("Tardaste mucho", ephemeral=True)
            return
        elif self.is_finished():
            await modal.interaction.response.send_message(
                "Tardaste mucho", ephemeral=True
            )
            return

        value = str(modal.page.value)
        if not value.isdigit():
            await modal.interaction.response.send_message(
                f"Esperado número, no {value!r}", ephemeral=True
            )
            return

        value = int(value)
        await self.show_checked_page(modal.interaction, value - 1)
        if not modal.interaction.response.is_done():
            error = modal.page.placeholder.replace("Enter", "Esperado")  # type: ignore # Can't be None
            await modal.interaction.response.send_message(error, ephemeral=True)

    @discord.ui.button(label="Cerrar", style=discord.ButtonStyle.red)
    async def stop_pages(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """stops the pagination session."""
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()


class FieldPageSource(menus.ListPageSource):
    """A page source that requires (field_name, field_value) tuple items."""

    def __init__(
        self,
        entries: list[tuple[Any, Any]],
        *,
        per_page: int = 12,
        inline: bool = False,
        clear_description: bool = True,
    ) -> None:
        super().__init__(entries, per_page=per_page)
        self.embed: discord.Embed = discord.Embed(colour=discord.Colour.blurple())
        self.clear_description: bool = clear_description
        self.inline: bool = inline

    async def format_page(
        self, menu: SpacePages, entries: list[tuple[Any, Any]]
    ) -> discord.Embed:
        self.embed.clear_fields()
        if self.clear_description:
            self.embed.description = None

        for key, value in entries:
            self.embed.add_field(name=key, value=value, inline=self.inline)

        maximum = self.get_max_pages()
        if maximum > 1:
            text = f"Pág. {menu.current_page + 1}/{maximum} ({len(self.entries)} resultados)"
            self.embed.set_footer(text=text)

        return self.embed


class TextPageSource(menus.ListPageSource):
    def __init__(self, text, *, prefix="```", suffix="```", max_size=2000):
        pages = CommandPaginator(prefix=prefix, suffix=suffix, max_size=max_size - 200)
        for line in text.split("\n"):
            pages.add_line(line)

        super().__init__(entries=pages.pages, per_page=1)

    async def format_page(self, menu, content):
        maximum = self.get_max_pages()
        if maximum > 1:
            return f"{content}\nPág. {menu.current_page + 1}/{maximum}"
        return content


class SimplePageSource(menus.ListPageSource):
    async def format_page(self, menu, entries):
        pages = []
        for index, entry in enumerate(entries, start=menu.current_page * self.per_page):
            pages.append(f"{index + 1}. {entry}")

        maximum = self.get_max_pages()
        if maximum > 1:
            footer = f"Pág. {menu.current_page + 1}/{maximum} ({len(self.entries)} resultados)"
            menu.embed.set_footer(text=footer)

        menu.embed.description = "\n".join(pages)
        return menu.embed


class SimplePages(SpacePages):
    """A simple pagination session reminiscent of the old Pages interface.

    Basically an embed with some normal formatting.
    """

    def __init__(self, entries, *, ctx: Context, per_page: int = 12):
        super().__init__(SimplePageSource(entries, per_page=per_page), ctx=ctx)
        self.embed = discord.Embed(colour=discord.Colour.blurple())


from jishaku.shim.paginator_200 import PaginatorEmbedInterface


ReferenceLike = Union[discord.Message, discord.PartialMessage, commands.Context]


class EmbedPaginator(PaginatorEmbedInterface):
    def __init__(
        self,
        bot: Bot,
        paginator: commands.Paginator,
        *,
        owner: discord.abc.User = discord.utils.MISSING,
        delete_message: bool = discord.utils.MISSING,
        timeout: float = discord.utils.MISSING,
        emoji: str = discord.utils.MISSING,
    ) -> None:
        kwargs: dict[str, Any] = {}

        for key, value in dict(
            owner=owner, delete_message=delete_message, timeout=timeout, emoji=emoji
        ).items():
            if value is not discord.utils.MISSING:
                kwargs[key] = value

        super().__init__(
            bot,
            paginator,
            **kwargs,
        )

        self.button_close.label = "\N{BLACK SQUARE FOR STOP} \u200b Cerrar"
        self.button_goto.label = "\N{RIGHTWARDS ARROW WITH HOOK} \u200b Ir a..."

    def update_view(self) -> None:
        super().update_view()
        self.button_close.label = f"{self.emojis.close} \u200b Cerrar"

    class PageChangeModal(discord.ui.Modal, title="Ir a la página"):
        page_number: discord.ui.TextInput[discord.ui.Modal] = discord.ui.TextInput(
            label="Página",
            style=discord.TextStyle.short,
        )

        def __init__(
            self, interface: "EmbedPaginator", *args: Any, **kwargs: Any
        ) -> None:
            super().__init__(*args, timeout=interface.timeout_length, **kwargs)
            self.interface = interface
            self.page_number.label = f"Página (1 - {interface.page_count})"
            self.page_number.min_length = 1
            self.page_number.max_length = len(str(interface.page_count))

        async def on_submit(self, itx: discord.Interaction) -> None:
            try:
                if not self.page_number.value:
                    raise ValueError("Page number not filled")
                self.interface.display_page = int(self.page_number.value) - 1
            except ValueError:
                await itx.response.send_message(
                    content=f"``{self.page_number.value}`` no es un número de página válido",
                    ephemeral=True,
                )
            else:
                self.interface.update_view()
                await itx.response.edit_message(**self.interface.send_kwargs)

    async def send_to(self, reference: ReferenceLike) -> EmbedPaginator:
        """Replies to the reference."""

        self.message: discord.Message = await reference.reply(
            **self.send_kwargs,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        self.send_lock.set()

        if self.task:
            self.task.cancel()

        self.task = self.bot.loop.create_task(self.wait_loop())

        return self

    @property
    def send_kwargs(self) -> Dict[str, Any]:
        display_page: int = self.display_page
        self._embed.description = self.pages[display_page]
        self._embed.color = self.bot.default_color  # type: ignore
        return {"embed": self._embed, "view": self}

    max_page_size = 2048

    @property
    def page_size(self) -> int:
        return self.paginator.max_size
