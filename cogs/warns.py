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
import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Optional, Literal, overload

import warnings
import discord
from discord.state import ConnectionState
from discord.ext import commands

from _types.bot import Bot
from _types.contextutil import ContextMenuHolder
from _types.warns import Warn, ActionType
from models import GuildUser, WarnsConfig

if TYPE_CHECKING:
    from _types.warns.protocols import Object

_log = logging.getLogger(__name__)


class MockMessageable:
    """Mock messageable that represents a missing channel"""

    @discord.utils.copy_doc(discord.abc.Messageable.send)
    async def send(
        self, content: Optional[str] = discord.utils.MISSING, **kwargs: Any
    ): ...

    @property
    def type(self) -> discord.ChannelType:
        return discord.ChannelType.text


class MissingAsset:
    """Mock asset"""

    @property
    def url(self) -> None:
        """:class:`str`: Returns the underlying URL of the asset."""
        return None


class MockMember:
    def __init__(self, guild_id: int, user_id: int, state: ConnectionState) -> None:
        self.guild_id: int = guild_id
        self.id: int = user_id
        self.state: ConnectionState = state

    @discord.utils.copy_doc(discord.Member.add_roles)
    async def add_roles(
        self,
        *roles: discord.abc.Snowflake,
        reason: str | None = None,
        atomic: bool = True,
    ) -> None:
        if not atomic:
            await self.state.http.edit_member(
                self.guild_id,
                self.id,
                reason=reason,
                **{"roles": tuple(r.id for r in roles)},
            )
        else:
            req = self.state.http.add_role
            guild_id = self.guild_id
            user_id = self.id
            for role in roles:
                await req(guild_id, user_id, role.id, reason=reason)

    @discord.utils.copy_doc(discord.Member.remove_roles)
    async def remove_roles(
        self,
        *roles: discord.abc.Snowflake,
        reason: str | None = None,
        atomic: bool = True,
    ) -> None:
        # We ignore atomic as we cannot access the previous member state roles
        for role in roles:
            await self.state.http.remove_role(
                self.guild_id, self.id, role.id, reason=reason
            )

    @discord.utils.copy_doc(discord.Member.timeout)
    async def timeout(
        self,
        until: datetime.timedelta | datetime.datetime | None,
        /,
        *,
        reason: str | None = None,
    ) -> None:
        if until is None:
            timed_out_until = None
        elif isinstance(until, datetime.timedelta):
            timed_out_until = discord.utils.utcnow() + until
        elif isinstance(until, datetime.datetime):
            timed_out_until = until
        else:
            raise TypeError(
                f"expected None, datetime.datetime, or datetime.timedelta not {until.__class__.__name__}"
            )
        await self.state.http.edit_member(
            self.guild_id,
            self.id,
            reason=reason,
            communication_disabled_until=(
                timed_out_until.isoformat() if timed_out_until is not None else None
            ),
        )

    @discord.utils.copy_doc(discord.Member.ban)
    async def ban(
        self,
        *,
        delete_message_days: int = discord.utils.MISSING,
        delete_message_seconds: int = discord.utils.MISSING,
        reason: str | None = None,
    ) -> None:
        if (
            delete_message_days is not discord.utils.MISSING
            and delete_message_seconds is not discord.utils.MISSING
        ):
            raise TypeError(
                "Cannot mix delete_message_days and delete_message_seconds keyword arguments."
            )

        if delete_message_days is not discord.utils.MISSING:
            msg = (
                "delete_message_days is deprecated, use delete_message_seconds instead"
            )
            warnings.warn(msg, DeprecationWarning, stacklevel=2)
            delete_message_seconds = delete_message_days * 86400  # one day

        if delete_message_seconds is discord.utils.MISSING:
            delete_message_seconds = 86400  # one day

        await self.state.http.ban(
            self.id,
            self.guild_id,
            delete_message_seconds,
            reason,
        )

    @discord.utils.copy_doc(discord.Member.kick)
    async def kick(self, *, reason: str | None = None) -> None:
        await self.state.http.unban(
            self.id,
            self.guild_id,
            reason=reason,
        )


class Warns(commands.Cog):
    """Comandos que permiten gestionar las advertencias"""

    def __init__(self, bot: Bot) -> None:
        self.bot: Bot = bot
        self._context_menu_holder: ContextMenuHolder = (
            ContextMenuHolder.partial_holder()
        )
        self._context_menu_holder.on_attach = self.on_attach

    def on_attach(self) -> None:
        self._context_menu_holder.load_commands_from(self)
        self._context_menu_holder.copy_to_tree()

    async def cog_load(self) -> None:
        self._context_menu_holder.attach(self.bot)

    async def cog_unload(self) -> None:
        for command in self._context_menu_holder.commands:
            self.bot.tree.remove_command(command.name, type=command.type)
            self._context_menu_holder.remove_command(command)

    @overload
    def _log_embed(
        self,
        action: Literal[ActionType.ban],
        data: Warn,
        warns: int,
    ) -> discord.Embed: ...

    @overload
    def _log_embed(
        self,
        action: Literal[ActionType.kick],
        data: Warn,
        warns: int,
    ) -> discord.Embed: ...

    @overload
    def _log_embed(
        self,
        action: Literal[ActionType.timeout],
        data: Warn,
        warns: int,
        *,
        duration: datetime.timedelta,
    ) -> discord.Embed: ...

    @overload
    def _log_embed(
        self,
        action: Literal[ActionType.role],
        data: Warn,
        warns: int,
        *,
        roles: Sequence[Object],
    ) -> discord.Embed: ...

    @overload
    def _log_embed(
        self,
        action: None,
        data: Warn,
        warns: int,
    ) -> discord.Embed: ...

    def _log_embed(
        self,
        action: Optional[ActionType],
        data: Warn,
        warns: int,
        *,
        roles: Sequence[Object] = discord.utils.MISSING,
        duration: datetime.timedelta = discord.utils.MISSING,
    ) -> discord.Embed:
        embed = discord.Embed(color=self.bot.default_color)
        embed.set_thumbnail(
            url=getattr(data.target, "display_avatar", MissingAsset()).url
        )
        embed.set_author(
            name=f"Staff responsable:",
            icon_url=getattr(data.staff, "display_avatar", MissingAsset()).url,
        )
        embed.description = f"<@{data.staff.id}>\n\nEl usuario <@{data.target.id}> ({data.target.id}) ha alcanzado {warns} warn(s)."

        if action is not None:
            if action == ActionType.kick:
                string = "El miembro fue expulsado"
            elif action == ActionType.ban:
                string = "El miembro fue baneado"
            elif action == ActionType.timeout:
                string = f'El miembro fue aislado temporalmente hasta {discord.utils.format_dt(datetime.datetime.now(datetime.UTC)+duration, style="R")}'
            elif action == ActionType.role:
                string = f'Se le añadieron los roles: {discord.utils._human_join([f"<@&{role.id}>" for role in roles], final="y")}'

            embed.add_field(
                name="Acción tomada:",
                value=string,
            )

        return embed

    @commands.Cog.listener("on_warn_add")
    async def on_warn_add(
        self, data: Warn, user_data: GuildUser, config: WarnsConfig
    ) -> Any:
        """Called when a warn is added"""

        warn_amount = len(user_data.warns.keys())
        if config.notifications is not None:
            guild = self.bot.get_guild(data.guild.id)
            if guild:
                log_channel = (
                    guild.get_channel(config.notifications) or MockMessageable()
                )
                if isinstance(
                    log_channel, (discord.ForumChannel, discord.CategoryChannel)
                ):
                    log_channel = MockMessageable()
            else:
                log_channel = MockMessageable()
        else:
            log_channel = MockMessageable()

        roles, timeouts, kicks, bans = config.config.get_punishments(warn_amount)

        if isinstance(data.target, discord.Object):
            data.target = MockMember(
                data.guild.id, data.target.id, self.bot._connection
            )

        if bans:
            ban = bans[0]

            await data.target.ban(reason=f"Ha llegado a {ban.n} warns")
            await log_channel.send(
                embed=self._log_embed(ActionType.ban, data, warn_amount)
            )
            return

        if kicks:
            kick = kicks[0]
            await data.target.kick(reason=f"Ha llegado a {kick.n} warns")
            await log_channel.send(
                embed=self._log_embed(ActionType.kick, data, warn_amount)
            )  # type: ignore
            return

        sent = False

        if timeouts:
            timeout = timeouts[0]

            await data.target.timeout(
                timeout.duration, reason=f"Ha alcanzado {timeout.n} warns"
            )
            await log_channel.send(
                embed=self._log_embed(ActionType.timeout, data, warn_amount, duration=timeout.duration)  # type: ignore
            )
            sent = True

        if roles:
            to_add: list[Object] = [role.role for role in roles]  # type: ignore
            await data.target.add_roles(
                *to_add, reason=f"Ha alcanzado {warn_amount} warns"
            )
            await log_channel.send(
                embed=self._log_embed(ActionType.role, data, warn_amount, roles=to_add)
            )  # type: ignore
            sent = True

        if not sent:
            await log_channel.send(
                embed=self._log_embed(None, data, warn_amount)
            )  # type: ignore

    @commands.Cog.listener()
    async def on_warn_remove(self, data: Warn) -> Any:
        """Called when a warn is removed"""

        config, _ = await WarnsConfig.get_or_create(
            guild=data.guild.id,
        )
        user, _ = await GuildUser.get_or_create(
            user=data.target.id,
            guild=data.guild.id,
        )

        if config.notifications is not None:
            partial = self.bot.get_partial_messageable(
                config.notifications,
                guild_id=data.guild.id,
            )
        else:
            partial = MockMessageable()

        warn_amount = len(user.warns.keys())
        roles, timeouts, *_ = config.config.get_punishments(
            warn_amount
        )  # if member was kicked or banned
        # we won't do anything about it, just
        # ignore, cuz ban, well, you're ban kid
        # cry about it

        if isinstance(data.guild, discord.Guild):
            guild = data.guild
            member = data.guild.get_member(data.target.id)
        else:
            guild = self.bot.get_guild(data.guild.id)

            if not guild:
                _log.debug(
                    "Discarding WARN_REMOVE event as not guild %s was found",
                    data.guild.id,
                )
                return

            member = guild.get_member(data.target.id)

        if not member:
            member = await guild.fetch_member(data.target.id)
            guild._add_member(member)  # pylint: disable=protected-access

        if roles:
            to_remove = [role.role for role in roles if role.role is not None]
            await member.remove_roles(
                *to_remove, reason="Se le quitaron las advertencias"
            )


async def setup(bot: Bot) -> None:
    await bot.add_cog(Warns(bot))
