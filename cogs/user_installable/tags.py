from __future__ import annotations

import discord, difflib
import discord.ext.commands
import discord.ext.menus
from discord import app_commands as commands

from typing import Any, Optional

from models import UserTagsPrivate
from _types import Bot
from cogs.utils.paginator import SpacePages, TextPageSource


async def get_user_tags(
    itx: discord.Interaction, current: str
) -> list[commands.Choice[str]]:
    """Autocomplete to get all available tags"""

    config = await UserTagsPrivate.get_or_none(id=itx.user.id)

    if not config:
        return []

    if not config.tags:
        config.tags = {}

    return [
        commands.Choice(name=tag, value=tag)
        for tag in difflib.get_close_matches(
            current, config.tags.keys(), n=25, cutoff=0.3
        )
    ]


class CreateTag(discord.ui.Modal):
    def __init__(
        self,
        config: UserTagsPrivate,
        *,
        default_content: Optional[str] = None,
        default_name: Optional[str] = None,
    ) -> None:
        super().__init__(title="Crear Etiqueta", timeout=None)
        self.config: UserTagsPrivate = config

        self.name: discord.ui.TextInput = discord.ui.TextInput(
            label="Nombre",
            style=discord.TextStyle.short,
            placeholder="...",
            required=True,
            default=default_name,
            max_length=20,
        )
        self.content: discord.ui.TextInput = discord.ui.TextInput(
            label="Contenido",
            style=discord.TextStyle.long,
            placeholder="...",
            required=True,
            default=default_content,
            max_length=2000,
        )

        self.add_item(self.name)
        self.add_item(self.content)

    async def on_submit(self, itx: discord.Interaction) -> None:
        name: str = self.name.value
        content: str = self.content.value

        if self.config.tags is None:
            self.config.tags = {}

        self.config.tags.update({name: content})

        await self.config.save()
        await itx.response.send_message(
            f"Se ha creado la etiqueta `{name}`", ephemeral=True
        )


class ChangeTagContent(discord.ui.Modal):
    def __init__(self, config: UserTagsPrivate, tag_name: str, content: str) -> None:
        super().__init__(title="Editar Etiqueta", timeout=None)

        self.name = discord.ui.TextInput(
            label="Nombre",
            style=discord.TextStyle.short,
            placeholder="...",
            required=True,
            default=tag_name,
            max_length=20,
        )
        self.content = discord.ui.TextInput(
            label="Contenido",
            style=discord.TextStyle.long,
            placeholder="...",
            required=True,
            default=content,
            max_length=2000,
        )

        self.add_item(self.name)
        self.add_item(self.content)

        self.config: UserTagsPrivate = config
        self.tag_name: str = tag_name

    async def on_submit(self, itx: discord.Interaction) -> None:
        content: str = "Se ha editado la etiqueta"

        if self.config.tags is None:
            self.config.tags = {}

        if self.name.value != self.tag_name:
            del self.config.tags[self.tag_name]
            self.config.tags[self.name.value] = self.content.value
            content += f", ahora llamada `{self.name.value}`"
        else:
            self.config.tags[self.tag_name] = self.content.value

        await self.config.save()
        await itx.response.send_message(content, ephemeral=True)


@commands.allowed_contexts(dms=True, private_channels=True, guilds=True)
@commands.allowed_installs(users=True, guilds=False)
class Tags(discord.ext.commands.GroupCog, name="tag"):
    """Permite gestionar etiquetas guardadas para tí."""

    def __init__(self, bot: Bot) -> None:
        self.bot: Bot = bot

        self.create_tag_from_message_ctxmenu: commands.ContextMenu = (
            commands.ContextMenu(
                name="Crear Etiqueta",
                callback=self.create_tag_from_message,
            )
        )

        self.bot.tree.add_command(self.create_tag_from_message_ctxmenu)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(
            self.create_tag_from_message_ctxmenu.name,
            type=self.create_tag_from_message_ctxmenu.type,
        )

    @commands.command(name="get")
    @commands.describe(tag="La etiqueta a obtener")
    @commands.autocomplete(tag=get_user_tags)
    @commands.checks.cooldown(1, 5)
    async def tag_get(self, itx: discord.Interaction, *, tag: str) -> Any:
        """Obtiene una etiqueta"""
        await itx.response.defer(thinking=True)

        config = await UserTagsPrivate.get_or_none(id=itx.user.id)
        if config is None:
            await UserTagsPrivate.create(id=itx.user.id, tags={})
            return await itx.followup.send("No tienes etiquetas", ephemeral=True)

        if not config.tags:
            return await itx.followup.send("No tienes etiquetas", ephemeral=True)

        if tag not in config.tags.keys():
            return await itx.followup.send(
                f"No tienes una etiqueta llamada `{tag}`", ephemeral=True
            )

        tag_content = config.tags.get(tag)

        if isinstance(tag_content, dict):  # If it is a dict, then is an alias
            tag_content = config.tags.get(tag_content.get("alias_for"))  # type: ignore

        if not tag_content:
            return await itx.followup.send(
                "No se ha podido cargar el contenido de la etiqueta, esto probablemente es un error del bot, no tuyo",
                ephemeral=True,
            )

        await itx.followup.send(tag_content)

    @commands.command(name="alias")
    @commands.describe(tag="La etiqueta original", name="El nombre del alias")
    @commands.autocomplete(tag=get_user_tags)
    @commands.checks.cooldown(1, 5)
    async def tag_alias(
        self, itx: discord.Interaction, tag: str, *, name: commands.Range[str, 1, 20]
    ) -> Any:
        """Crea un alias a una etiqueta"""
        await itx.response.defer(thinking=True, ephemeral=True)

        config = await UserTagsPrivate.get_or_none(id=itx.user.id)

        if config is None:
            await UserTagsPrivate.create(id=itx.user.id)
            return await itx.followup.send("No tienes etiquetas", ephemeral=True)

        if not config.tags:
            return await itx.followup.send("No tienes etiquetas", ephemeral=True)

        if tag not in config.tags:
            return await itx.followup.send(
                f"No tienes una etiqueta llamada `{tag}`", ephemeral=True
            )

        config.tags.update({name: {"alias_for": tag}})
        await config.save()

        await itx.followup.send(
            f"Se ha creado el alias `{name}` que redirige a `{tag}`", ephemeral=True
        )

    @commands.command(name="create")
    @commands.describe(
        name="El nombre de la etiqueta a crear",
        content="El contenido que el bot mandará cuando obtengas la etiqueta",
    )
    @commands.checks.cooldown(1, 5)
    async def tag_create(
        self,
        itx: discord.Interaction,
        name: commands.Range[str, 1, 20],
        *,
        content: commands.Range[str, 1, 2000],
    ) -> Any:
        """Crea una nueva etiqueta para poder obtenerla más tarde"""
        await itx.response.defer(thinking=True, ephemeral=True)

        config, _ = await UserTagsPrivate.get_or_create(
            id=itx.user.id, defaults={"tags": {}}
        )

        if config.tags is None:
            config.tags = {}

        if name in config.tags:
            return await itx.followup.send(
                f"Ya existe una etiqueta llamada `{name}`", ephemeral=True
            )

        config.tags.update({name: content})
        await config.save()

        await itx.followup.send(f"Se ha creado la etiqueta `{name}`", ephemeral=True)

    @commands.command(name="make")
    @commands.checks.cooldown(1, 5)
    async def tag_make(self, itx: discord.Interaction) -> None:
        """Crea una etiqueta de manera interactiva"""
        config, _ = await UserTagsPrivate.get_or_create({"tags": {}}, id=itx.user.id)

        if not config.tags:
            config.tags = {}

        await itx.response.send_modal(CreateTag(config=config))

    @commands.command(name="delete")
    @commands.describe(tag="La etiqueta a borrar")
    @commands.autocomplete(tag=get_user_tags)
    @commands.checks.cooldown(1, 15)
    async def tag_delete(self, itx: discord.Interaction, *, tag: str) -> None:
        """Elimina una etiqueta"""
        await itx.response.defer(thinking=True, ephemeral=True)
        config = await UserTagsPrivate.get_or_none(id=itx.user.id)

        if not config or not config.tags:
            return await itx.followup.send(
                "No tienes etiquetas para borrar", ephemeral=True
            )

        if tag not in config.tags:
            return await itx.followup.send(
                f"No tienes ninguna etiqueta llamada `{tag}`", ephemeral=True
            )

        config.tags.pop(tag)
        await config.save()
        await itx.followup.send(f"Has borrado la etiqueta `{tag}`", ephemeral=True)

    @commands.command(name="edit")
    @commands.describe(tag="La etiqueta a editar")
    @commands.autocomplete(tag=get_user_tags)
    @commands.checks.cooldown(1, 10)
    async def tag_edit(self, itx: discord.Interaction, *, tag: str) -> None:
        """Edita una etiqueta"""
        config = await UserTagsPrivate.get_or_none(id=itx.user.id)

        if not config or not config.tags:
            return await itx.response.send_message(
                "No tienes etiquetas para editar", ephemeral=True
            )

        if tag not in config.tags:
            return await itx.response.send_message(
                f"No existe ninguna etiqueta llamada `{tag}`", ephemeral=True
            )

        tag_content: Optional[str] = config.tags.get(tag, None)

        if not tag_content:
            return await itx.response.send_message(
                "No se ha podido cargar el contenido de la etiqueta, esto probablemente es un error del bot, no tuyo",
                ephemeral=True,
            )

        await itx.response.send_modal(ChangeTagContent(config, tag, tag_content))

    @commands.command(name="list")
    @commands.checks.cooldown(1, 5)
    async def tag_list(self, itx: discord.Interaction) -> None:
        """Muestra todas tus etiquetas"""
        await itx.response.defer(thinking=True, ephemeral=True)
        config = await UserTagsPrivate.get_or_none(id=itx.user.id)

        if not config:
            await UserTagsPrivate(id=itx.user.id).save()
            return await itx.followup.send("No tienes etiquetas", ephemeral=True)

        if not config.tags:
            return await itx.followup.send("No tienes etiquetas", ephemeral=True)

        ctx = await discord.ext.commands.Context.from_interaction(itx)

        text: str = ""

        for tag, content in config.tags.items():
            text += f"`{tag}`"

            if isinstance(content, dict):
                text += f' (alias de `{content.get("alias_for")}`)\n'
            else:
                text += "\n"

        source = TextPageSource(text, prefix=None, suffix=None)  # type: ignore
        menu = SpacePages(source, ctx=ctx, check_embeds=False, compact=False)  # type: ignore

        await menu.start(ephemeral=True)

    # @commands.context_menu()
    @commands.checks.cooldown(1, 10)
    @commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.allowed_installs(guilds=False, users=True)
    async def create_tag_from_message(
        self, itx: discord.Interaction, message: discord.Message
    ) -> None:
        """Crea una etiqueta a partir del contenido de un mensaje"""
        config, _ = await UserTagsPrivate.get_or_create({"tags": {}}, id=itx.user.id)
        if config.tags is None:
            config.tags = {}

        await itx.response.send_modal(
            CreateTag(config, default_content=message.content)
        )
