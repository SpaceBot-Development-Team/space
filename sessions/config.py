from __future__ import annotations

from typing import Optional, Protocol, TYPE_CHECKING

import discord
from discord.member import Member
from discord.ui.view import View

from _types.context import GuildContext as Context
from _types.views import ConfigView, StrikesView, WarnsView
from _types.embeds import AlterRole, StrikesEmbed, WarnsEmbed
from _types.warns import WarnConfig as WarnConfigModel
from models import (
    Guild,
    VouchsConfig,
    WarnsConfig,
)

if TYPE_CHECKING:
    from typing_extensions import Self

# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring


class SessionProto(Protocol):
    if TYPE_CHECKING:
        invoker: Member
        _context: Context | None

    def instance_view(self) -> View: ...

    @classmethod
    async def from_context(cls, ctx: Context) -> Self: ...

    async def start(self) -> None: ...


class ConfigSession:
    def __init__(self, invoker: Member, config: Guild, vouch_cfg: VouchsConfig) -> None:
        self.invoker: Member = invoker
        self.config: Guild = config
        self.vouch_cfg: VouchsConfig = vouch_cfg
        self._context: Context = discord.utils.MISSING

    @property
    def context(self) -> Context:
        return self._context

    @context.setter
    def context(self, obj: Context) -> None:
        self._context = obj

    def instance_view(self) -> ConfigView:
        return ConfigView(self.config, self.vouch_cfg)

    @classmethod
    async def from_context(cls, ctx: Context) -> ConfigSession:
        cfg, _ = await Guild.get_or_create(id=ctx.guild.id)
        vouch, _ = await VouchsConfig.get_or_create(id=ctx.guild.id)
        instance = cls(ctx.author, cfg, vouch)
        instance.context = ctx

        return instance

    async def start(self) -> None:
        """Starts the config session"""

        await self.context.reply(
            view=self.instance_view(),
            embed=AlterRole(cfg=self.config, vouchs=self.vouch_cfg),
        )  # type: ignore


class StrikesConfigSession:
    def __init__(self, invoker: Member, config: Guild) -> None:
        self.invoker: Member = invoker
        self.config: Guild = config

        self._context: Context = discord.utils.MISSING

    @property
    def context(self) -> Context:
        return self._context

    @context.setter
    def context(self, obj: Context) -> None:
        self._context = obj

    @classmethod
    async def from_context(cls, ctx: Context) -> StrikesConfigSession:
        cfg: Optional[Guild] = await Guild.filter(id=ctx.guild.id).get_or_none()

        if not cfg:
            cfg = await Guild.create(id=ctx.guild.id, enabled=True, prefix="!")

        instance = cls(ctx.author, cfg)
        instance.context = ctx

        return instance

    def instance_view(self) -> StrikesView:
        return StrikesView(self.invoker, self.config)

    async def start(self) -> None:
        """Starts the config session"""

        await self.context.reply(
            view=self.instance_view(),
            embed=StrikesEmbed(cfg=self.config, guild=self.context.guild),
        )  # type: ignore


class WarnsConfigSession:
    def __init__(self, invoker: Member, config: WarnsConfig) -> None:
        self.invoker: Member = invoker
        self.config: WarnsConfig = config

        self._context: Context = discord.utils.MISSING

        self.model = self.config.config

    @property
    def context(self) -> Context:
        return self._context

    @context.setter
    def context(self, obj: Context) -> None:
        self._context = obj

    @classmethod
    async def from_context(cls, ctx: Context) -> WarnsConfigSession:
        cfg: WarnsConfig | None = await WarnsConfig.get_or_none(
            guild=ctx.guild.id,
        )

        if not cfg:
            cfg = await WarnsConfig.create(
                guild=ctx.guild.id,
                enabled=False,
                config=WarnConfigModel.from_params(
                    roles=[],
                    bans=[],
                    kicks=[],
                    timeouts=[],
                    metadata=None,
                ),
            )
        instance = cls(ctx.author, cfg)
        instance.context = ctx

        return instance

    def instance_view(self) -> WarnsView:
        return WarnsView(self.invoker, self.config)

    async def start(self) -> None:
        await self.context.reply(
            view=self.instance_view(),
            embed=WarnsEmbed(cfg=self.config, guild=self.context.guild),
        )  # type: ignore
