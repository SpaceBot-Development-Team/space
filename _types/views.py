# pylint: disable=too-many-lines, redefined-outer-name, unused-argument, wrong-import-order, missing-class-docstring, missing-function-docstring, arguments-renamed, arguments-differ, line-too-long
# type: ignore
"""Multiple View subclasses"""
from __future__ import annotations

import asyncio
import datetime
from typing import Final, List, Tuple, TypeVar, Callable

import copy
import re
import json
from io import BytesIO

import wavelink
import humanfriendly
import discord

from discord.embeds import Embed
from discord.colour import Color
from discord.errors import HTTPException
from discord.partial_emoji import PartialEmoji
from discord.enums import ButtonStyle, TextStyle, ChannelType
from discord.message import Message
from discord.interactions import Interaction
from discord.member import Member as DPYMember
from discord.ui.view import View as ViewT
from discord.ui.button import button, Button
from discord.components import SelectOption
from discord.ui.select import select, RoleSelect, ChannelSelect, Select
from discord.ui.modal import Modal
from discord.ui.text_input import TextInput
from discord.enums import try_enum

from .embeds import (
    AlterRole,
    StrikesEmbed,
    WarnsEmbed,
)
from .bot import Bot as Orbyt
from .context import Context
from .interactions import GuildInteraction
from .warns import ActionType, WarnAction, Warn

from models import (
    Guild,
    GuildUser,
    VouchsConfig,
    WarnsConfig,
)

PAUSED = False
ENABLED = True
T = TypeVar(
    "T",
)
V = TypeVar(
    "V",
)
EMOJIS = {
    "yes": "✅",
    "no": "❌",
    "white_x": "✖",
    "white_minus": "➖",
    "white_plus": "➕",
    "white_pencil": "✏",
    "channel_text": "🗨",
}
HTTP_URL_REGEX = r"https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)"
cprint: Callable[..., None] = print
SPACE_PREMIUM_SKU_ID: Final[int] = 1256218013930094682


def truncate(string: str, width: int = 50) -> str:
    if len(string) > width:
        string = string[: width - 3] + "..."
    return string


def re_url_match(url: str):
    return re.fullmatch(HTTP_URL_REGEX, url)


def message_jump_button(url: str, to_where: str = "al Mensaje"):
    if not re_url_match(url):
        raise ValueError
    return Button(label=f"Ve {to_where}", style=ButtonStyle.url, url=url)


def generate_help_embed() -> discord.Embed:
    emb = discord.Embed(
        title="Título",
        url="http://example.com/orbyt",
        description="Esta es la _descripción_ del embed.\n"
        "La descripción puede ser de hasta **4000** caracteres.\n"
        "Hay un límite conjunto de **6000** caracteres (incluyendo nuevas líneas) para los embeds.\n"
        "Ten en cuenta que la descripción se puede __separar en múltiples líneas__.",
        color=CONTRAST_COLOR,
    )

    emb.set_author(
        name="<< Icono de Autor | Nombre de Autor",
        url="http://example.com/orbyt",
        icon_url="https://i.imgur.com/KmwxpHF.png",
    )

    emb.set_footer(
        text="<< Icono de Pie del Embed | Este es el Pie del Embed",
        icon_url="https://i.imgur.com/V8xDSE5.png",
    )

    for i in range(1, 3):
        emb.add_field(
            name=f"Línea {i}",
            value=f"El texto de la línea {i}\nEs en la misma línea",
            inline=True,
        )

    emb.add_field(
        name="Línea 3",
        value="El texto de la línea 3\nNO es en la misma línea",
        inline=False,
    )

    emb.set_image(url="https://i.imgur.com/EhtHWap.png")
    emb.set_thumbnail(url="https://i.imgur.com/hq8nDF2.png")

    return emb


MISSING = discord.utils.MISSING
CONTRAST_COLOR: discord.Color = discord.Color.from_str("#755ae0")


class BaseView(ViewT):
    def _map_interaction_entitlements_sku_ids(
        self, entitlement: discord.Entitlement
    ) -> int:
        return entitlement.sku_id

    def is_premium_interaction(self, interaction: Interaction) -> bool:
        entitlement_sku_ids = map(
            self._map_interaction_entitlements_sku_ids, interaction.entitlements
        )
        if SPACE_PREMIUM_SKU_ID not in entitlement_sku_ids:
            return False

    def create_sku_required_view(self, sku_id: int) -> ViewT:
        view = ViewT()
        view.add_item(Button(style=ButtonStyle.premium, sku_id=sku_id))
        return view


class WarningSelect(Select["SelectUserWarning"]):
    def __init__(self, warns: dict[str, Warn], cfg: GuildUser):
        self.cfg = cfg
        options: list[SelectOption] = []

        for warn_id, reason in warns.items():
            options.append(
                SelectOption(
                    label=f"ID: {warn_id}",
                    description=reason.reason,
                    value=warn_id,
                )
            )

        super().__init__(
            placeholder="Selecciona la advertencia...",
            min_values=1,
            max_values=1,
            options=options[:25],
            disabled=False,
            row=0,
        )

    async def callback(self, itx: Interaction) -> None:  # type: ignore
        warn = self.cfg.warns.pop(self.values[0])
        await self.cfg.save()
        await itx.response.edit_message(
            view=None,
            content=f"Se ha quitado la advertencia ID `{self.values[0]}` de <@{self.cfg.user}>. Su razón fue: `{warn.reason}`",
        )
        new = Warn.from_data(id=self.values[0], data=warn, state=itx._state)
        itx.client.dispatch("warn_remove", new)
        self.view.stop()  # type: ignore


class SelectUserWarning(BaseView):
    def __init__(self, cfg: GuildUser, invoker: DPYMember) -> None:
        self.cfg = cfg
        self.invoker = invoker

        self.original_message: Message = None  # type: ignore

        super().__init__(timeout=180 * 2)
        self.add_item(WarningSelect(self.cfg.warns, self.cfg))

    async def interaction_check(self, itx: Interaction) -> bool:
        if not self.original_message:
            self.original_message = itx.message  # type: ignore

        return self.invoker.id == itx.user.id

    async def on_timeout(self) -> None:
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True

        await self.original_message.edit(view=self)


class ChangePrefix(Modal):
    def __init__(self, config: Guild, original_message: Message) -> None:
        self.config: Guild = config
        self.vouchs: VouchsConfig = MISSING
        self.prefix: TextInput = TextInput(
            label="Nuevo Prefijo",
            style=TextStyle.short,
            max_length=5,
            row=0,
            default=config.prefix,
        )
        self.original: Message = original_message

        super().__init__(title="Cambiar el prefijo", timeout=180)
        loop = asyncio.get_running_loop()
        loop.create_task(self.on_instation())

        self.add_item(self.prefix)

    async def on_instation(self) -> None:
        """..."""
        self.vouchs, _ = await VouchsConfig.get_or_create(
            id=self.config.id,
        )

    async def on_submit(self, itx: Interaction[Orbyt]) -> None:
        self.config.prefix = self.prefix.value
        await self.config.save()

        await itx.response.send_message(
            f"Se cambió el prefijo a `{self.config.prefix}`", ephemeral=True
        )
        itx.client.guild_prefixes[itx.guild_id] = self.prefix.value
        await self.original.edit(embed=AlterRole(cfg=self.config, vouchs=self.vouchs))


class ConfigView(BaseView):
    """Config session view"""

    def __init__(self, config: Guild, vouchs: VouchsConfig) -> None:
        self.config: Guild = config
        self.vouchs: VouchsConfig = vouchs
        self.original_message: Message | None = None

        super().__init__(timeout=180 * 2)

        if not config.enabled:
            self.edit_properties(PAUSED, self.toggle_pause)

        if vouchs.command_like:
            self.toggle_command_like.label = "Manual"
            self.toggle_command_like.style = ButtonStyle.gray
            self.toggle_command_like.emoji = "✍"

        if not vouchs.enabled:
            self.toggle_vouchs.label = "Vouchs Deshabilitados"
            self.toggle_vouchs.style = ButtonStyle.red
            self.toggle_vouchs.emoji = "❌"

            self.toggle_command_like.disabled = True
            self.select_whitelisted_channels.disabled = True

    async def on_timeout(self) -> None:
        for child in self.children:
            if hasattr(child, "disabled"):
                setattr(child, "disabled", True)

        if self.original_message:
            await self.original_message.edit(view=self)
        self.stop()

    async def interaction_check(self, i: GuildInteraction) -> bool:
        if not self.original_message:
            self.original_message = i.message

        perms = i.channel.permissions_for(i.user)

        return perms.manage_guild

    @staticmethod
    def is_paused(button: Button) -> bool:
        return (
            button.style == ButtonStyle.red
            and "deshabilitado" in button.label.lower()
            and button.emoji != PartialEmoji(name="✅", animated=False, id=None)
        )

    def edit_properties(self, to: bool, obj: T) -> T:
        if to:
            obj.label = "Bot Habilitado"
            obj.style = ButtonStyle.green
            obj.emoji = "✅"

        else:
            obj.label = "Bot Deshabilitado"
            obj.style = ButtonStyle.red
            obj.emoji = "❌"

        return obj

    @button(
        label="Bot Habilitado",
        style=ButtonStyle.green,
        emoji="✅",
        row=0,
    )
    async def toggle_pause(self, i: Interaction, button: Button) -> None:
        if self.is_paused(button):
            self.edit_properties(ENABLED, button)
            self.alter_roles.disabled = False
            self.toggle_vouchs.disabled = False
        else:
            self.edit_properties(PAUSED, button)
            self.alter_roles.disabled = True
            self.toggle_vouchs.disabled = True

        self.config.enabled = not self.is_paused(button)
        await self.config.save()

        await i.response.edit_message(view=self)

    @button(label="Cambiar prefijo", style=ButtonStyle.blurple, emoji="🗒", row=0)
    async def change_prefix(self, i: Interaction, _: Button) -> None:
        await i.response.send_modal(ChangePrefix(self.config, i.message))

    @select(
        cls=RoleSelect, placeholder="Rol de alter...", min_values=1, max_values=1, row=1
    )
    async def alter_roles(self, i: Interaction, select: RoleSelect) -> None:
        self.config.alter = select.values[0].id
        await self.config.save()

        await i.response.edit_message(
            embed=AlterRole(cfg=self.config, vouchs=self.vouchs)
        )

    @button(label="Vouchs Habilitados", style=ButtonStyle.green, emoji="✅", row=2)
    async def toggle_vouchs(self, itx: Interaction, button: Button) -> None:
        if self.is_paused(button):
            button.label = "Vouchs Habilitados"
            button.style = ButtonStyle.green
            button.emoji = "✅"

            self.toggle_command_like.disabled = False
            self.select_whitelisted_channels.disabled = False

            self.vouchs.enabled = True

        else:
            button.label = "Vouchs Deshabilitados"
            button.style = ButtonStyle.red
            button.emoji = "❌"

            self.toggle_command_like.disabled = True
            self.select_whitelisted_channels.disabled = True

            self.vouchs.enabled = False

        await self.vouchs.save()
        await itx.response.edit_message(
            view=self,
            embed=AlterRole(cfg=self.config, vouchs=self.vouchs),
        )

    @button(label="Automático", style=ButtonStyle.blurple, emoji="🤖", row=2)
    async def toggle_command_like(self, itx: Interaction, button: Button) -> None:
        if button.label == "Manual":
            button.label = "Automático"
            button.style = ButtonStyle.blurple
            button.emoji = "🤖"

            self.vouchs.command_like = False

        else:
            button.label = "Manual"
            button.style = ButtonStyle.grey
            button.emoji = "✍"

            self.vouchs.command_like = True

        await self.vouchs.save()
        await itx.response.edit_message(
            view=self,
            embed=AlterRole(cfg=self.config, vouchs=self.vouchs),
        )

    @select(
        cls=ChannelSelect,
        channel_types=[
            ChannelType.text,
            ChannelType.news,
        ],
        placeholder="Elige los canales permitidos de comandos...",
        max_values=5,
        row=3,
    )
    async def select_whitelisted_channels(
        self, itx: Interaction, select: ChannelSelect
    ) -> None:
        self.vouchs.whitelisted_channels = [channel.id for channel in select.values]

        await self.vouchs.save()
        await itx.response.edit_message(
            embed=AlterRole(cfg=self.config, vouchs=self.vouchs)
        )


class StrikesView(BaseView):
    def __init__(self, inv: DPYMember, cfg: Guild) -> None:
        self.inv = inv
        self.cfg: Guild = cfg

        self.original_message: Message = None

        super().__init__(timeout=180 * 2)

    async def on_timeout(self) -> None:
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True

        await self.original_message.edit(view=self)
        self.stop()

    async def interaction_check(self, itx: Interaction) -> bool:
        if not self.original_message:
            self.original_message = itx.message

        return itx.user.id == self.inv.id

    @select(
        cls=ChannelSelect,
        min_values=1,
        max_values=1,
        placeholder="Para staffs...",
        channel_types=[ChannelType.text, ChannelType.news],
        row=0,
    )
    async def staff_select(self, itx: Interaction, select: ChannelSelect) -> None:
        self.cfg.staff_report = select.values[0].id

        await self.cfg.save()
        await itx.response.edit_message(
            embed=StrikesEmbed(cfg=self.cfg, guild=itx.guild)
        )

    @select(
        cls=ChannelSelect,
        min_values=1,
        max_values=1,
        placeholder="Para usuarios...",
        channel_types=[ChannelType.text, ChannelType.news],
        row=1,
    )
    async def user_select(
        self, itx: Interaction, select: ChannelSelect["StrikesView"]
    ) -> None:
        self.cfg.user_report = select.values[0].id

        await self.cfg.save()
        await itx.response.edit_message(
            embed=StrikesEmbed(cfg=self.cfg, guild=itx.guild)
        )


class WarnsView(BaseView):
    def __init__(self, invoker: DPYMember, cfg: WarnsConfig) -> None:
        self.invoker = invoker
        self.cfg = cfg

        self.original_message: Message = MISSING
        self.guild_config: Guild = MISSING
        loop = asyncio.get_running_loop()
        loop.create_task(self.on_instation())

        super().__init__(timeout=180 * 2)

        if not cfg.enabled:
            self.toggle_warns.label = "Warns Deshabilitadas"
            self.toggle_warns.style = ButtonStyle.red
            self.toggle_warns.emoji = "❌"

            self.add_punishment.disabled = True

        if cfg.config.total_punishments() <= 0:
            self.remove_punishment.disabled = True

    async def on_instation(self) -> None:
        self.guild_config, _ = await Guild.get_or_create(id=self.invoker.guild.id)

    async def interaction_check(self, itx: Interaction) -> bool:
        if self.original_message is MISSING:
            self.original_message = itx.message  # type: ignore

        return itx.user.id == self.invoker.id

    async def on_timeout(self) -> None:
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True

        if self.original_message is not discord.utils.MISSING:
            await self.original_message.edit(view=self)
        self.stop()

    @button(
        label="Warns Habilitadas",
        disabled=False,
        style=ButtonStyle.green,
        emoji="✅",
        row=0,
    )
    async def toggle_warns(self, itx: Interaction, button: Button["WarnsView"]) -> None:
        if "warns habilitadas" == button.label.lower():  # type: ignore
            button.label = "Warns Deshabilitadas"
            button.style = ButtonStyle.red
            button.emoji = "❌"

            self.cfg.enabled = False
            self.add_punishment.disabled = True
            self.remove_punishment.disabled = True

        else:
            button.label = "Warns Habilitadas"
            button.style = ButtonStyle.green
            button.emoji = "✅"

            self.cfg.enabled = True
            self.add_punishment.disabled = False
            self.remove_punishment.disabled = False

        await self.cfg.save()
        embed = WarnsEmbed(cfg=self.cfg, guild=itx.guild)  # type: ignore
        embed.color = itx.message.embeds[0].color  # type: ignore

        await itx.response.edit_message(embed=embed, view=self)

    @button(
        label="Añadir Acción",
        disabled=False,
        emoji="\N{MEMO}",
        row=0,
    )
    async def add_punishment(
        self, itx: Interaction, button: Button["WarnsView"]
    ) -> None:
        if (
            self.cfg.config.total_punishments() >= 10
            and not self.is_premium_interaction(itx)
        ):
            await itx.response.send_message(
                "¡Necesitas Space Premium para poder añadir más de 10 acciones de advertencias!",
                view=self.create_sku_required_view(SPACE_PREMIUM_SKU_ID),
            )
            return
        modal = AddPunishmentModal(self.cfg, self.original_message, self)
        await itx.response.send_modal(modal)

    @button(
        label="Quitar Acción",
        disabled=False,
        emoji="\N{CROSS MARK}",
        row=0,
    )
    async def remove_punishment(
        self, itx: Interaction, button: Button["WarnsView"]
    ) -> None:
        if self.cfg.config.total_punishments() <= 0:
            await itx.response.send_message(
                "No hay acciones para quitar",
                ephemeral=True,
            )
            return
        await itx.response.send_message(
            "Envía en cuantas warns se cumple la acción (``n`` warns), tienes 1 minuto:",
            ephemeral=True,
        )
        try:
            message = await itx.client.wait_for(
                "message",
                check=lambda m: (
                    m.author.id == itx.user.id and m.channel.id == itx.channel_id
                ),
                timeout=60.0,
            )
        except asyncio.TimeoutError:
            await itx.followup.send(
                "Tardaste mucho en responder, la operación se ha cancelado",
                ephemeral=True,
            )
            return

        if not message.content.isdigit():
            await itx.followup.send(
                f"El contenido del mensaje no es válido como número (`{message.content}`), inténtalo de nuevo.",
                ephemeral=True,
            )
            return

        n = int(message.content)

        await message.delete()

        if all(not p for p in self.cfg.config.get_punishments(n)):
            await itx.followup.send(
                f"No hay acciones para cuando un usuario llega a {n} warns",
                ephemeral=True,
            )
            return

        view = SelectPunishment(self.cfg, self.original_message, n, self)

        await itx.followup.send(
            "Selecciona la acción que quitar",
            view=view,
            ephemeral=True,
        )

    @select(
        cls=ChannelSelect,
        channel_types=[
            discord.ChannelType.text,
            discord.ChannelType.news,
            discord.ChannelType.voice,
            discord.ChannelType.stage_voice,
        ],
        max_values=1,
        placeholder="Escoger canal de registros...",
    )
    async def change_logs_channel(
        self, itx: Interaction, sct: ChannelSelect["WarnsView"]
    ) -> None:
        """..."""
        self.cfg.notifications = sct.values[0].id
        await self.cfg.save()
        await itx.response.edit_message(
            embed=WarnsEmbed(cfg=self.cfg, guild=itx.guild)  # type: ignore
        )


class AddPunishmentModal(Modal):

    punishment_type = TextInput(
        label="Tipo de castigo (role | timeout | kick | ban)",
        style=TextStyle.short,
        placeholder="role | timeout | kick | ban",
        min_length=3,
        max_length=7,
    )
    warns = TextInput(
        label="Cantidad de warns",
        style=TextStyle.short,
        max_length=10,
    )

    def __init__(
        self, cfg: WarnsConfig, original: Message, original_view: WarnsView
    ) -> None:
        self.config: WarnsConfig = cfg
        self.original: Message = original
        self.original_view: WarnsView = original_view

        super().__init__(
            title="Crear Castigo",
        )

    async def on_submit(self, interaction: Interaction, /) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)

        punishment_type = try_enum(ActionType, self.punishment_type.value.lower())

        if punishment_type.name.startswith("unknown_"):
            await interaction.followup.send(
                f"Se ha proporcionado un tipo de acción inválido: {self.punishment_type.value} "
                "recuerda que solo se permiten ``role``, ``timeout``, ``kick`` o ``ban``.",
            )
            return

        if not self.warns.value.isdigit():
            await interaction.followup.send(
                f"El valor porporcionado no es un número válido ({self.warns.value})",
            )
            return

        n = int(self.warns.value)

        if punishment_type == ActionType.role:
            await interaction.followup.send(
                "Elige el rol a dar para cuando este castigo se cumpla:",
                view=SelectWarnRole(self.config, self.original, n, self.original_view),
            )
        elif punishment_type == ActionType.timeout:
            await interaction.followup.send(
                "¿Cuánto durará el aislamiento? (1d, 3h) (máximo de 28 días), tienes 1 minuto para contestar:",
                ephemeral=True,
            )
            try:
                message = await interaction.client.wait_for(
                    "message",
                    check=lambda m: (
                        m.author.id == interaction.user.id
                        and m.channel.id == interaction.channel_id
                    ),
                    timeout=60.0,
                )
            except asyncio.TimeoutError:
                await interaction.followup.edit_message(
                    (await interaction.original_response()).id,
                    content="Tardaste mucho en responder",
                )
                return

            content = message.content
            await message.delete()

            try:
                time = humanfriendly.parse_timespan(content)
            except humanfriendly.InvalidTimespan:
                await interaction.followup.send(
                    f"El texto `{content}` no es válido como una duración",
                    ephemeral=True,
                )
                return

            if time > 2419200.0:
                await interaction.followup.send(
                    "El tiempo excede el límite, que son 28 días.",
                    ephemeral=True,
                )
                return

            try:
                self.config.config.create_punishment(
                    n=n,
                    type=ActionType.timeout,
                    duration=datetime.timedelta(seconds=time),
                )
            except ValueError:
                await interaction.followup.send(
                    "Una acción que es exactamente igual ya existe.",
                    ephemeral=True,
                )
                return

            if self.original_view.remove_punishment.disabled:
                self.original_view.remove_punishment.disabled = False

            if (
                self.config.config.total_punishments() >= 10
                and not self.original_view.guild_config.premium
            ):
                self.original_view.add_punishment.disabled = True

            await self.config.save()
            await interaction.followup.send(
                "Se ha añadido la acción",
                ephemeral=True,
            )
            await self.original.edit(
                embed=WarnsEmbed(cfg=self.config, guild=interaction.guild),  # type: ignore
                view=self.original_view,
            )

        else:
            try:
                self.config.config.create_punishment(n=n, type=punishment_type)
            except ValueError:
                await interaction.followup.send(
                    "Una acción que es exactamente igual ya existe.",
                    ephemeral=True,
                )
                return
            await self.config.save()

            if self.original_view.remove_punishment.disabled:
                self.original_view.remove_punishment.disabled = False

            if (
                self.config.config.total_punishments() >= 10
                and not self.original_view.guild_config.premium
            ):
                self.original_view.add_punishment.disabled = True

            await self.original.edit(
                embed=WarnsEmbed(cfg=self.config, guild=interaction.guild),  # type: ignore
                view=self.original_view,
            )
        self.stop()


class SelectWarnRole(BaseView):
    def __init__(
        self, config: WarnsConfig, original: Message, n: int, original_view: WarnsView
    ) -> None:
        self.config: WarnsConfig = config
        self.original: Message = original
        self.n: int = n
        self.original_view: WarnsView = original_view

        super().__init__(timeout=None)

    @select(
        cls=RoleSelect,
        placeholder="Escoge un rol...",
        min_values=1,
        max_values=1,
        row=0,
    )
    async def role_select(
        self, itx: Interaction, select: RoleSelect["SelectWarnRole"]
    ) -> None:
        await itx.response.defer(thinking=True, ephemeral=True)
        value = select.values[0]

        try:
            self.config.config.create_punishment(
                n=self.n,
                type=ActionType.role,
                role=value,
            )
        except ValueError:
            await itx.followup.send(
                "Una acción que es exactamente igual ya existe.",
                ephemeral=True,
            )
            return

        await self.config.save()
        await itx.edit_original_response(
            content="Se ha establecido el rol",
            view=None,
        )

        if self.original_view.remove_punishment.disabled:
            self.original_view.remove_punishment.disabled = False

        if (
            self.config.config.total_punishments() >= 10
            and not self.original_view.guild_config.premium
        ):
            self.original_view.add_punishment.disabled = True

        await self.original.edit(
            embed=WarnsEmbed(
                cfg=self.config,
                guild=itx.guild,  # type: ignore
            ),
            view=self.original_view,
        )
        self.stop()


class SelectPunishment(BaseView):
    def __init__(
        self, config: WarnsConfig, original: Message, n: int, original_view: WarnsView
    ):
        self.config: WarnsConfig = config
        self.original: Message = original
        self.original_view: WarnsView = original_view
        super().__init__(timeout=None)
        r_punishments: Tuple[List[WarnAction], ...] = config.config.get_punishments(n)
        punishments = r_punishments[0] + r_punishments[1] + r_punishments[2]

        for punish in punishments[:25]:
            self.punishment_select.add_option(  # pylint: disable=no-member
                label=f"{punish.n} Warns - {punish.type.name}",
                value=str(punish.id),
            )

    @select(cls=Select["SelectPunishment"], min_values=1, max_values=1, row=0)
    async def punishment_select(
        self, itx: Interaction, select_t: Select["SelectPunishment"]
    ) -> None:
        """..."""

        value = int(select_t.values[0])
        # value is now an ID

        punishment = self.config.config.get_punishment(value)
        if not punishment:
            await itx.response.send_message(
                f"Un error extraño ha ocurrido, no se ha podido encontrar la acción con ID ``{value}``. :thinking:",
                ephemeral=True,
            )
            return

        self.config.config.remove_punishment(punishment.id)
        await self.config.save()

        await itx.response.edit_message(
            view=None,
            content="Se ha eliminado esa acción",
        )

        if self.config.config.total_punishments() <= 0:
            self.original_view.remove_punishment.disabled = True

        await self.original.edit(
            embed=WarnsEmbed(cfg=self.config, guild=self.original.guild),  # type: ignore
            view=self.original_view,
        )
        self.stop()


class ChangeVolume(Modal):
    def __init__(self, m_id: int, player: wavelink.Player, /) -> None:
        self.player: wavelink.Player = player
        self.m_id: int = m_id

        self.volume = TextInput(
            label="Nuevo volumen:",
            style=TextStyle.short,
            max_length=3,
            min_length=1,
            default=str(player.volume),
        )

        super().__init__(title="Cambiar volumen")

        self.add_item(self.volume)

    async def on_submit(self, itx: Interaction) -> None:
        await itx.response.defer()
        await self.player.set_volume(int(self.volume.value))
        await itx.followup.edit_message(
            self.m_id, view=EditPlayer(itx.user, self.player)
        )


class EditPlayer(BaseView):
    def __init__(self, author: DPYMember, player: wavelink.Player, /) -> None:
        self.player: wavelink.Player = player
        self.message: Message = None
        self.author: DPYMember = author

        super().__init__(timeout=180 * 4)

        self.change_volume.label = f"Volumen: {player.volume}%"

        if player.autoplay == wavelink.AutoPlayMode.enabled:
            if player.queue.mode == wavelink.QueueMode.loop_all:
                self.change_queue_mode.emoji = "🔁"
                self.change_queue_mode.style = ButtonStyle.green

            elif player.queue.mode == wavelink.QueueMode.loop:
                self.change_queue_mode.emoji = "🔂"
                self.change_queue_mode.style = ButtonStyle.blurple

        else:
            self.change_queue_mode.disabled = True

    async def interaction_check(self, itx: Interaction) -> None:
        if not self.message:
            self.message = itx.message

        return itx.user.id == self.author.id

    async def on_timeout(self) -> None:
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True

        await self.message.edit(view=self)

    @button(label="Volumen: 30%", style=ButtonStyle.blurple, disabled=False, row=0)
    async def change_volume(self, itx: Interaction, _: Button["EditPlayer"]) -> None:
        await itx.response.send_modal(ChangeVolume(itx.message.id, self.player))

    @button(
        emoji="❌",
        row=0,
        style=ButtonStyle.red,
    )
    async def change_queue_mode(
        self, itx: Interaction, btn: Button["EditPlayer"]
    ) -> None:
        if str(btn.emoji) == "❌":
            btn.emoji = "🔁"
            btn.style = ButtonStyle.green

            self.player.queue.mode = wavelink.QueueMode.loop_all

        elif str(btn.emoji) == "🔁":
            btn.emoji = "🔂"
            btn.style = ButtonStyle.blurple

            self.player.queue.mode = wavelink.QueueMode.loop

        elif str(btn.emoji) == "🔂":
            btn.emoji = "❌"
            btn.style = ButtonStyle.red

            self.player.queue.mode = wavelink.QueueMode.normal

        await itx.response.edit_message(view=self)


# EMBED BUILDER


class EmbedModal(Modal):
    def __init__(self, *, _embed: Embed, parent_view: BaseView) -> None:
        self.embed = _embed
        self.parent_view = parent_view

        self.em_title.default = _embed.title
        self.em_desc.default = _embed.description

        if _image := _embed.image:
            self.image.default = _image.url

        if _thumbnail := _embed.thumbnail:
            self.thumbnail.default = _thumbnail.url

        if _embed.color:
            rgb = _embed.color.to_rgb()

            self.color.default = f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})"

        super().__init__(title="Editar Componentes", timeout=None)

    em_title = TextInput(
        label="Título",
        placeholder="El título del embed",
        style=TextStyle.short,
        required=False,
        max_length=256,
    )

    em_desc = TextInput(
        label="Descripción",
        placeholder="Hasta 4000 caracteres. De cantidad máxima compartida (6000)\nLorem ipsum dolor sit amet.\n",
        style=TextStyle.long,
        required=False,
        max_length=4000,
    )

    image = TextInput(
        label="URL de Imagen",
        placeholder="http://example.com/space.png",
        required=False,
        style=TextStyle.short,
    )

    thumbnail = TextInput(
        label="URL de Miniatura",
        placeholder="http://example.com/stars.png",
        required=False,
        style=TextStyle.short,
    )

    color = TextInput(
        label="Color", placeholder="Hex #FFFFFF | rgb(r, g, b)", required=False
    )

    async def on_submit(self, itx: Interaction) -> None:
        embed_copy = copy.deepcopy(self.embed)

        self.embed.title = self.em_title.value
        self.embed.description = self.em_desc.value

        self.embed.set_image(url=self.image.value)
        self.embed.set_thumbnail(url=self.thumbnail.value)

        if self.color.value:
            self.embed.color = Color.from_str(self.color.value)

        if len(self.embed) > 6000:
            self.parent_view.embed = embed_copy
            return await itx.response.send_message(
                "❌ - El embed es muy largo; Excedido el límite de 6000 caracteres.",
                ephemeral=True,
            )

        self.parent_view.update_counters()

        await itx.response.edit_message(embed=self.embed, view=self.parent_view)

    async def on_error(self, itx: Interaction, error: Exception) -> None:
        if isinstance(error, ValueError) or isinstance(error, HTTPException):
            await itx.response.send_message(
                "❌ - Error de Valor. Por favor comprueba lo siguiente:\n"
                "Embed Vacío / Color no Válido / URL(s) no válida(s)",
                ephemeral=True,
            )
        else:
            raise error


class AuthorModal(Modal):
    def __init__(self, *, embed: Embed, parent_view: BaseView) -> None:
        self.embed = embed
        self.parent_view = parent_view

        self.author.default = embed.author.name
        self.url.default = embed.author.url
        self.icon.default = embed.author.icon_url

        super().__init__(title="Editar Autor", timeout=None)

    author = TextInput(
        label="Nombre del Autor",
        placeholder="El nombre del autor",
        style=TextStyle.short,
        max_length=256,
        required=False,
    )

    url = TextInput(
        label="URL del Autor",
        placeholder="http://example.com",
        required=False,
        style=TextStyle.short,
    )

    icon = TextInput(
        label="URL de Icono de Autor",
        placeholder="http://example.com/astronaut.png",
        required=False,
        style=TextStyle.short,
    )

    async def on_submit(self, itx: Interaction) -> None:
        embed_copy = copy.deepcopy(self.embed)

        self.embed.set_author(
            name=self.author.value, url=self.url.value, icon_url=self.icon.value
        )

        if len(self.embed) > 6000:
            self.parent_view.embed = embed_copy

            return await itx.response.send_message(
                "❌ - El embed es muy largo; Excedido el límite de 6000 caracteres.",
                ephemeral=True,
            )

        self.parent_view.update_counters()
        await itx.response.edit_message(embed=self.embed, view=self.parent_view)

    async def on_error(self, itx: Interaction, error: Exception) -> None:
        if isinstance(error, (ValueError, HTTPException)):
            await itx.response.send_message(
                "❌ - Error de Valor. Por favor comprueba lo siguiente:\n"
                "URL(s) inválida(s)",
                ephemeral=True,
            )

        else:
            raise error


class FooterModal(Modal):
    def __init__(self, *, embed: Embed, parent_view: BaseView) -> None:
        self.embed = embed
        self.parent_view = parent_view

        self.text.default = embed.footer.text
        self.url.default = embed.footer.icon_url

        super().__init__(title="Editar Pie de Embed", timeout=None)

    text = TextInput(
        label="Pie de Embed",
        placeholder="El texto del pie de embed",
        style=TextStyle.short,
        max_length=2048,
        required=False,
    )

    url = TextInput(
        label="URL de Icono de Pie de Embed",
        placeholder="http://example.com/austronaut.png",
        required=False,
        style=TextStyle.short,
    )

    async def on_submit(self, itx: Interaction) -> None:
        embed_copy = copy.deepcopy(self.embed)

        self.embed.set_footer(text=self.text.value, icon_url=self.url.value)

        if len(self.embed) > 6000:
            self.parent_view.embed = embed_copy

            return await itx.response.send_message(
                "❌ - El embed es muy largo; Excedido el límite de 6000 caracteres.",
                ephemeral=True,
            )

        self.parent_view.update_counters()
        await itx.response.edit_message(embed=self.embed, view=self.parent_view)


class URLModal(discord.ui.Modal):
    def __init__(self, *, _embed: discord.Embed, parent_view: discord.ui.View) -> None:
        self.embed = _embed

        self.parent_view = parent_view

        self.url.default = _embed.url

        super().__init__(title="Editar URL", timeout=None)

    url = TextInput(
        label="URL del Título ('none'=borrar)",
        placeholder="http://example.com",
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        embed_copy = copy.deepcopy(self.embed)

        if not self.embed.title:
            await interaction.response.send_message(
                f"{EMOJIS['no']} - El embed ha de tener un título.", ephemeral=True
            )
            return

        self.embed.url = self.url.value if self.url.value.lower() != "none" else None

        if len(self.embed) > 6000:
            self.parent_view.embed = embed_copy
            await interaction.response.send_message(
                f"{EMOJIS['no']} - El embed es muy largo; Excedido el límite de 6000 caracteres.",
                ephemeral=True,
            )
            return

        self.parent_view.update_counters()
        await interaction.response.edit_message(embed=self.embed, view=self.parent_view)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        if isinstance(error, ValueError) or isinstance(
            error, discord.errors.HTTPException
        ):
            await interaction.response.send_message(
                f"{EMOJIS['no']} - Error de Valor. URL Inválida.",
                ephemeral=True,
            )
        else:
            raise error


class AddFieldModal(discord.ui.Modal):
    def __init__(self, *, _embed: discord.Embed, parent_view: discord.ui.View) -> None:
        self.embed = _embed
        self.parent_view = parent_view

        super().__init__(title="Añadir Línea", timeout=None)

    fl_name = TextInput(
        label="Nombre de Línea",
        placeholder="El nombre de la línea",
        style=discord.TextStyle.short,
        max_length=256,
        required=True,
    )
    value = TextInput(
        label="Texto de Línea",
        placeholder="El texto de la línea",
        style=discord.TextStyle.long,
        max_length=1024,
        required=True,
    )
    inline = TextInput(
        label="¿En la misma línea?",
        placeholder="True/False | T/F || Yes/No | Y/N (predeterminado: True)",
        style=discord.TextStyle.short,
        max_length=5,
        required=False,
    )
    index = TextInput(
        label="Index (Dónde añadir la línea)",
        placeholder="1 - 25 (predeterminado: 25)",
        style=discord.TextStyle.short,
        max_length=2,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        embed_copy = copy.deepcopy(self.embed)

        inline_set = {
            "true": True,
            "t": True,
            "yes": True,
            "y": True,
            "false": False,
            "f": False,
            "no": False,
            "n": False,
        }
        if self.inline.value:
            inline = inline_set.get(self.inline.value.lower())
        else:
            inline = True

        index = (
            int(self.index.value) - 1 if self.index.value else len(self.embed.fields)
        )

        self.embed.insert_field_at(
            index,
            name=self.fl_name.value,
            value=self.value.value,
            inline=inline,
        )

        if len(self.embed) > 6000:
            self.parent_view.embed = embed_copy

            await interaction.response.send_message(
                f"{EMOJIS['no']} - El embed es muy largo; Excedido el límite de 6000 caracteres.",
                ephemeral=True,
            )
            return

        self.parent_view.update_counters()
        await interaction.response.edit_message(embed=self.embed, view=self.parent_view)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        if isinstance(error, ValueError) or isinstance(
            error, discord.errors.HTTPException
        ):
            await interaction.response.send_message(
                f"{EMOJIS['no']} - Error de Valor. {str(error)}",
                ephemeral=True,
            )
        else:
            cprint(
                f"{error} {type(error)} {isinstance(error, discord.HTTPException)}",
                "red",
            )
            raise error


class DeleteFieldDropdown(discord.ui.Select):
    def __init__(
        self,
        *,
        _embed: discord.Embed,
        parent_view: discord.ui.View,
        original_msg: discord.Message,
    ):
        self.embed = _embed

        self.parent_view = parent_view

        self.original_msg = original_msg

        options = [
            discord.SelectOption(
                label=truncate(f"{i+1}. {field.name}"),
                value=str(i),
            )
            for i, field in enumerate(self.embed.fields)
        ]

        super().__init__(
            placeholder="Elige una Línea", min_values=1, max_values=1, options=options
        )

    async def callback(self, interaction: discord.Interaction):
        self.embed.remove_field(int(self.values[0]))
        if len(self.embed) == 0:
            self.embed.description = "Lorem ipsum dolor sit amet."

        self.parent_view.update_counters()
        await self.original_msg.edit(embed=self.embed, view=self.parent_view)
        await interaction.response.edit_message(
            content=f"{EMOJIS['yes']} - Línea eliminada.", view=None
        )


class EditFieldModal(discord.ui.Modal):
    fl_name = TextInput(
        label="Nombre de Línea",
        placeholder="El nombre de la línea",
        style=discord.TextStyle.short,
        max_length=256,
        required=False,
    )
    value = TextInput(
        label="Texto de Línea",
        placeholder="El texto de la línea",
        style=discord.TextStyle.long,
        max_length=1024,
        required=False,
    )
    inline = TextInput(
        label="¿En la misma línea?",
        placeholder="True/False | T/F || Yes/No | Y/N",
        style=discord.TextStyle.short,
        max_length=5,
        required=False,
    )
    index = TextInput(
        label="Index (Dónde añadir la línea)",
        placeholder="1 - 25 (predeterminado: 25)",
        style=discord.TextStyle.short,
        max_length=2,
        required=False,
    )

    def __init__(
        self,
        *,
        _embed: discord.Embed,
        parent_view: discord.ui.View,
        field_index: int,
        original_msg: discord.Message,
    ) -> None:
        self.embed = _embed

        self.parent_view = parent_view
        self._old_index = int(field_index)

        self.original_msg = original_msg

        field = self.embed.fields[field_index]

        self.fl_name.default = field.name
        self.value.default = field.value
        self.inline.default = str(field.inline)
        self.index.default = str(field_index + 1)

        super().__init__(title=f"Editando la Línea: {field_index+1}", timeout=None)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        embed_copy = copy.deepcopy(self.embed)

        inline_set = {
            "true": True,
            "t": True,
            "yes": True,
            "y": True,
            "false": False,
            "f": False,
            "no": False,
            "n": False,
        }
        inline = inline_set.get(self.inline.value.lower())

        if self.index.value:
            index = int(self.index.value) - 1
        else:
            index = len(self.embed.fields) - 1

        if index < 0 or index > len(self.embed.fields):
            raise IndexError("Index fuera de rango.")

        if inline is None:
            raise ValueError("¡El valor de la misma línea ha de ser un Booleano!")

        self.embed.remove_field(self._old_index)
        self.embed.insert_field_at(
            index, name=self.fl_name.value, value=self.value.value, inline=inline
        )

        if len(self.embed) > 6000:
            self.parent_view.embed = embed_copy

            await interaction.response.send_message(
                f"{EMOJIS['no']} - El embed es muy largo; Excedido el límite de 6000 caracteres.",
                ephemeral=True,
            )
            return

        self.parent_view.update_counters()
        await self.original_msg.edit(embed=self.embed, view=self.parent_view)

        await interaction.response.edit_message(
            content=f"{EMOJIS['yes']} - Línea editada.", view=None
        )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        if isinstance(error, ValueError) or isinstance(
            error, discord.errors.HTTPException
        ):
            await interaction.response.edit_message(
                content=f"{EMOJIS['no']} - Valor no válido: {str(error)}",
                view=None,
            )
        elif isinstance(error, IndexError):
            await interaction.response.edit_message(
                content=f"{EMOJIS['no']} - Index no válido: {str(error)}",
                view=None,
            )
        else:
            raise error


class EditFieldDropdown(discord.ui.Select):
    def __init__(
        self,
        *,
        _embed: discord.Embed,
        parent_view: discord.ui.View,
        original_msg: discord.Message,
    ):
        self.embed = _embed
        self.parent_view = parent_view
        self.original_msg = original_msg

        options = [
            discord.SelectOption(
                label=truncate(f"{i+1}. {field.name}", 100),
                value=str(i),
            )
            for i, field in enumerate(_embed.fields)
        ]

        super().__init__(
            placeholder="Elige una Línea", min_values=1, max_values=1, options=options
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            EditFieldModal(
                _embed=self.embed,
                field_index=int(self.values[0]),
                original_msg=self.original_msg,
                parent_view=self.parent_view,
            )
        )
        await interaction.edit_original_response(view=None, content="Editando Línea...")


class SendToChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, *, _embed: discord.Embed, bot: Orbyt):
        self.embed = _embed
        self.bot = bot

        super().__init__(
            placeholder="Elige un canal",
            channel_types=[
                ChannelType.text,
                ChannelType.news,
                ChannelType.private_thread,
                ChannelType.public_thread,
                ChannelType.voice,
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        # check if user has access to send messages to channel
        channel_id = self.values[0].id

        channel = self.bot.get_channel(channel_id)

        user_perms = channel.permissions_for(interaction.user)

        try:
            if user_perms.send_messages and user_perms.embed_links:
                msg = await channel.send(embed=self.embed)

                async def interaction_check(itx: Interaction) -> bool:
                    return interaction.user.id == itx.user.id

                confirmed_view = BaseView(
                    timeout=180,
                ).add_item(message_jump_button(msg.jump_url))
                confirmed_view.interaction_check = interaction_check
                await interaction.response.edit_message(
                    content=f"{EMOJIS['yes']} - Embed enviado a {channel.mention}.",
                    view=confirmed_view,
                )
            else:
                await interaction.response.edit_message(
                    content=f"{EMOJIS['no']} - No tienes permisos de enviar mensajes ni insertar enlaces en {channel.mention}.",
                    view=None,
                )
        except discord.HTTPException:
            await interaction.response.edit_message(
                f"{EMOJIS['no']} - No se pudo enviar el embed en {channel.mention}.",
                view=None,
            )


class SendViaWebhookModal(discord.ui.Modal):
    def __init__(self, *, _embed: discord.Embed):
        self.embed = _embed

        super().__init__(
            title="Enviar vía Webhook",
        )

    wh_url = discord.ui.TextInput(
        label="URL del Webhook",
        required=True,
        placeholder="URL del Webhook",
    )
    wh_name = discord.ui.TextInput(
        label="Nombre del Webhook",
        placeholder="Nombre del webhook (opcional)",
        required=False,
        max_length=80,
    )
    wh_avatar = discord.ui.TextInput(
        label="URL del Avatar del Webhook",
        placeholder="Avatar del webhook (opcional)",
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        mtch = re.fullmatch(
            r"https?:\/\/discord\.com\/api\/webhooks\/\d+\/.+",
            self.wh_url.value,
        )

        if not mtch:
            await interaction.response.send_message(
                f"{EMOJIS['no']} - URL Inválida",
                ephemeral=True,
            )
            return

        try:
            webhook = discord.Webhook.from_url(
                self.wh_url.value, session=interaction.client.session
            )

            msg = await webhook.send(
                username=self.wh_name.value or MISSING,
                avatar_url=self.wh_avatar.value or MISSING,
                embed=self.embed,
                wait=True,
            )

            await interaction.response.send_message(
                f"{EMOJIS['yes']} - Embed enviado [vía webhook]({self.wh_url.value}).",
                ephemeral=True,
                view=BaseView().add_item(message_jump_button(msg.jump_url)),
            )
        except discord.HTTPException:
            await interaction.response.send_message(
                f"{EMOJIS['no']} - No se pudo enviar el embed.",
                ephemeral=True,
            )


class ImportJSONModal(discord.ui.Modal):
    def __init__(self, *, _embed: discord.Embed, parent_view: discord.ui.View):
        self.embed = _embed
        self.parent_view = parent_view

        super().__init__(
            title="Importar JSON",
        )

    json_or_mystbin = discord.ui.TextInput(
        label="JSON",
        placeholder="Introduce el JSON del embed",
        required=True,
        style=discord.TextStyle.paragraph,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        json_value = self.json_or_mystbin.value

        to_dict = json.loads(
            json_value,
            parse_int=lambda x: int(x),
            parse_float=lambda x: float(x),
        )
        embed = discord.Embed.from_dict(to_dict)

        if len(embed) <= 0 or len(embed) > 6000:
            raise ValueError("Los caracteres del embed no son 0-6000")

        self.parent_view.embed = embed
        self.parent_view.update_counters()

        await interaction.edit_original_response(embed=embed, view=self.parent_view)
        await interaction.followup.send(
            content=f"{EMOJIS['yes']} - Embed importado desde JSON",
            ephemeral=True,
        )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        if isinstance(error, ValueError) or isinstance(
            error, discord.errors.HTTPException
        ):
            await interaction.followup.send(
                content=f"{EMOJIS['no']} - Error: {str(error)}", ephemeral=True
            )
        elif isinstance(error, json.JSONDecodeError):
            await interaction.followup.send(
                f"{EMOJIS['no']} - JSON no válido.",
                ephemeral=True,
            )
        else:
            raise error


class EmbedBuilderView(BaseView):
    def __init__(self, *, timeout: int, target: Context, **kwgs):
        self.bot = target.bot
        self.target = target
        super().__init__(
            timeout=timeout,
        )

        self.embed = kwgs.pop("embed", discord.Embed())

    async def interaction_check(self, itx: Interaction) -> bool:
        return itx.user.id == self.target.author.id

    def update_counters(self):
        self.character_counter.label = f"{len(self.embed)}/6000 Caracteres"
        self.field_counter.label = f"{len(self.embed.fields)}/25 Líneas"

    @discord.ui.button(
        label="Editar:", style=discord.ButtonStyle.gray, disabled=True, row=0
    )
    async def _basic_tag(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()

    @discord.ui.button(label="Embed", style=discord.ButtonStyle.primary, row=0)
    async def edit_embed(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(
            EmbedModal(_embed=self.embed, parent_view=self)
        )

    @discord.ui.button(label="Autor", style=discord.ButtonStyle.primary, row=0)
    async def edit_author(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(
            AuthorModal(embed=self.embed, parent_view=self)
        )

    @discord.ui.button(label="Pie", style=discord.ButtonStyle.primary, row=0)
    async def edit_footer(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(
            FooterModal(embed=self.embed, parent_view=self)
        )

    @discord.ui.button(label="URL", style=discord.ButtonStyle.primary, row=0)
    async def edit_url(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(
            URLModal(_embed=self.embed, parent_view=self)
        )

    @discord.ui.button(
        label="Líneas:", style=discord.ButtonStyle.gray, disabled=True, row=1
    )
    async def _fields_tag(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()

    @discord.ui.button(
        emoji=EMOJIS["white_plus"], style=discord.ButtonStyle.green, row=1
    )
    async def add_field(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if len(self.embed.fields) == 25:
            await interaction.response.send_message(
                f"{EMOJIS['no']} - Límite de 25 líneas alcanzado.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(
            AddFieldModal(_embed=self.embed, parent_view=self)
        )

    @discord.ui.button(
        emoji=EMOJIS["white_minus"], style=discord.ButtonStyle.red, row=1
    )
    async def delete_field(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if len(self.embed.fields) == 0:
            return await interaction.response.send_message(
                f"{EMOJIS['no']} - No hay líneas para borrar.", ephemeral=True
            )

        async def interaction_check(itx: Interaction) -> bool:
            return self.target.author.id == itx.user.id

        view = BaseView(timeout=180)
        view.interaction_check = interaction_check
        view.add_item(
            DeleteFieldDropdown(
                _embed=self.embed, original_msg=interaction.message, parent_view=self
            ),
        )
        await interaction.response.send_message(
            f"{EMOJIS['white_minus']} - Elige una línea que borrar:",
            view=view,
            ephemeral=True,
        )

    @discord.ui.button(
        emoji=EMOJIS["white_pencil"], style=discord.ButtonStyle.primary, row=1
    )
    async def edit_field(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if len(self.embed.fields) == 0:
            return await interaction.response.send_message(
                f"{EMOJIS['no']} - No hay líneas que editar.", ephemeral=True
            )

        async def interaction_check(itx: Interaction) -> bool:
            return self.target.author.id == itx.user.id

        view = BaseView(
            timeout=180,
        )
        view.interaction_check = interaction_check
        view.add_item(
            EditFieldDropdown(
                _embed=self.embed,
                parent_view=self,
                original_msg=interaction.message,
            ),
        )
        await interaction.response.send_message(
            f"{EMOJIS['white_pencil']} - Elige una línea que editar:",
            view=view,
            ephemeral=True,
        )

    @discord.ui.button(
        label="Enviar:", style=discord.ButtonStyle.gray, disabled=True, row=2
    )
    async def send_tag(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()

    @discord.ui.button(label="A Canal", style=discord.ButtonStyle.green, row=2)
    async def send_to_channel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if len(self.embed) == 0:
            return await interaction.response.send_message(
                f"{EMOJIS['no']} - ¡El embed está vacío!", ephemeral=True
            )

        async def interaction_check(itx: Interaction) -> bool:
            return self.target.author.id == itx.user.id

        view = BaseView(timeout=180)
        view.interaction_check = interaction_check
        view.add_item(SendToChannelSelect(_embed=self.embed, bot=self.bot))
        await interaction.response.send_message(
            f"{EMOJIS['channel_text']} - Elige el canal en el que enviar el embed:",
            view=view,
            ephemeral=True,
        )

    @discord.ui.button(label="Vía Webhook", style=discord.ButtonStyle.green, row=2)
    async def send_via_webhook(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if len(self.embed) == 0:
            return await interaction.response.send_message(
                f"{EMOJIS['no']} - ¡El embed está vacío!", ephemeral=True
            )

        await interaction.response.send_modal(SendViaWebhookModal(_embed=self.embed))

    @discord.ui.button(label="A MD", style=discord.ButtonStyle.green, row=2)
    async def send_to_dm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if len(self.embed) == 0:
            return await interaction.response.send_message(
                f"{EMOJIS['no']} - ¡El embed está vacío!", ephemeral=True
            )
        try:
            msg = await interaction.user.send(embed=self.embed)
            jump_view = discord.ui.View().add_item(message_jump_button(msg.jump_url))
            await interaction.response.send_message(
                f"{EMOJIS['yes']} - Embed enviado a tu MD.",
                ephemeral=True,
                view=jump_view,
            )
        except discord.HTTPException:
            await interaction.response.send_message(
                f"{EMOJIS['no']} - No se pudo enviar el embed a tus MDs.",
                ephemeral=True,
            )

    @discord.ui.button(label="Ayuda", style=discord.ButtonStyle.gray, row=3)
    async def help_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        em1 = generate_help_embed()
        em2 = discord.Embed(
            color=CONTRAST_COLOR,
        )
        em2.add_field(
            name="Fields",
            inline=False,
            value=f"{EMOJIS['white_plus']} Añadir Línea\n"
            f"{EMOJIS['white_minus']} Eliminar Línea\n"
            f"{EMOJIS['white_pencil']} Editar Línea (o reodenar)",
        )
        em2.add_field(
            name="JSON",
            inline=False,
            value=f"**Exportar a JSON**: Exporta el embed a un JSON válido para Discord.\n"
            f"**Importar JSON**: Importa el embed a partir de un JSON.",
        )
        await interaction.response.send_message(embeds=[em1, em2], ephemeral=True)

    @discord.ui.button(label="Exportar a JSON", style=discord.ButtonStyle.gray, row=3)
    async def export_json(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if len(self.embed) == 0:
            return await interaction.response.send_message(
                f"{EMOJIS['no']} - ¡El embed está vacío!", ephemeral=True
            )
        json_cont = json.dumps(self.embed.to_dict(), indent=4)
        stream = BytesIO(json_cont.encode())

        file = discord.File(fp=stream, filename="embed.json")
        await interaction.response.send_message(
            content="Aquí está tu embed exportado a JSON:", file=file, ephemeral=True
        )

    @discord.ui.button(label="Importar JSON", style=discord.ButtonStyle.gray, row=3)
    async def import_json(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(
            ImportJSONModal(_embed=self.embed, parent_view=self)
        )

    @discord.ui.button(emoji=EMOJIS["white_x"], style=discord.ButtonStyle.red, row=3)
    async def cancel_btn(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        for children in self.children:
            if hasattr(children, "disabled"):
                setattr(children, "disabled", True)
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(
        label="0/6000 Caracteres",
        disabled=True,
        style=discord.ButtonStyle.gray,
        row=4,
    )
    async def character_counter(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()

    @discord.ui.button(
        label="0/25 Líneas",
        disabled=True,
        style=discord.ButtonStyle.gray,
        row=4,
    )
    async def field_counter(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
