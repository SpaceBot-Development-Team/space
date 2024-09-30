"""Multiple embed subclasses"""

from __future__ import annotations

import humanfriendly
from discord import Color, Embed as EmbedT, Guild as DpyGuild

from .abc import MentionableMissing
from models import (
    Guild,
    VouchsConfig,
    WarnsConfig,
)


class AlterRole(EmbedT):
    """Embed to represent an Alter showing"""

    def __init__(
        self,
        *,
        cfg: Guild,
        vouchs: VouchsConfig,
    ) -> None:
        v_enabled = vouchs.enabled
        v_command_like = vouchs.command_like
        whitelisted_channels = vouchs.whitelisted_channels
        prefix = cfg.prefix or "!"

        description = (
            f'Bot habilitado: {"Sí" if cfg.enabled else "No"}\n'
            f"El rol configurado como alter es: <@&{cfg.alter}>\n"
            f'El prefijo actual del bot es: `{prefix or "!"}`'
        )
        v_description = (
            f'Vouchs habilitados: {"Sí" if v_enabled else "No"}\n'
            f'Vouchs añadidos mediante el comando `{cfg.prefix}vouch`: {"Sí" if v_command_like else "No, añadidos automáticamente"}\n'
        )

        if v_command_like:
            v_description += f'Canales permitidos de uso del comando: {", ".join([f"<#{id}>" for id in whitelisted_channels])}'
        else:
            v_description += f'Canales en los que se añadirá automáticamente: {", ".join([f"<#{id}>" for id in whitelisted_channels])}'

        super().__init__(
            color=Color.random(),
            description=description,
        )

        self.add_field(name="Configuración de Vouchs", value=v_description)


class StrikesEmbed(EmbedT):
    """Embed to represent an Strikes showing"""

    def __init__(self, *, cfg: Guild, guild: DpyGuild) -> None:
        staffs = (
            guild.get_channel(cfg.staff_report)
            if cfg.staff_report
            else MentionableMissing(cfg.staff_report, "missing")
        )
        users = (
            guild.get_channel(cfg.user_report)
            if cfg.user_report
            else MentionableMissing(cfg.user_report, "missing")
        )

        if not staffs:
            staffs = MentionableMissing(cfg.staff_report, "channel")
        if not users:
            users = MentionableMissing(cfg.user_report, "channel")

        super().__init__(
            title="Configuración de strikes",
            description=(
                f"Canal de reporte de staffs (strikes): {staffs.mention}\n"
                f"Canal de reportes de usuarios (sanciones): {users.mention}"
            ),
            color=Color.random(seed=guild.icon.url if guild.icon else 0),
        )


class WarnsEmbed(EmbedT):
    """Embed to represent a Warns showing"""

    def __init__(self, *, cfg: WarnsConfig, guild: DpyGuild) -> None:
        enabled = cfg.enabled
        data = cfg.config

        title = "Configuración de Warns"
        description = str()

        if enabled:
            description += "- ✅ | Warns Habilitados\n"
        else:
            description += "- ❌ | Warns Deshabilitados\n"

        super().__init__(color=Color.blurple(), title=title, description=description)

        if guild.icon:
            self.set_thumbnail(url=guild.icon.url)

        if cfg.notifications is not None:
            self.add_field(
                name="Canal de registros",
                value=f"<#{cfg.notifications}>",
                inline=False,
            )

        if data is not None:
            actions = sorted(
                (data.roles + data.timeouts + data.kicks + data.bans),
                key=lambda i: i.n,
                reverse=True,
            )

            for action in actions:
                rs = ""

                if action.role is not None:
                    rs = f"\nSe le dará el rol <@&{action.role.id}>"

                if action.duration is not None:
                    rs = f"\nEl aislamiento durará {humanfriendly.format_timespan(action.duration, False)}"

                self.add_field(
                    name=f"Advertencia Nº: {action.n}",
                    value=f"Tipo de acción: {action.type.name}" + rs,
                )
