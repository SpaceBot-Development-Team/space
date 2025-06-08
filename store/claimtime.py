"""
The MIT License (MIT)

Copyright (c) 2025-present Developer Anonymous

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

from typing import TYPE_CHECKING

import discord

from .core import DBStore

if TYPE_CHECKING:
    from bot import LegacyBot

__all__ = ('ClaimtimeDBStore',)


class ClaimtimeDBStore(DBStore):
    """A :class:`DBStore` subclass that automatically implements the logic for
    managing claimtimes.

    Parameters
    ----------
    bot: :class:`LegacyBot`
        The bot.
    """

    def __init__(self, bot: LegacyBot) -> None:
        super().__init__(
            bot,
            'claimtimes_config',
            'guild_id',
        )

    def get_member_claimtime(self, member: discord.Member, /) -> float | None:
        """Gets and returns a member's claimtime, or ``None``.

        Parameters
        ----------
        member: :class:`discord.Member`
            The member to obtain the claimtime from.

        Returns
        -------
        Optional[:class:`float`]
            The claimtime, or ``None``.
        """

        config = self.get(member.guild.id)

        if config is None:
            return None

        base = 0
        roles = [r.id for r in member.roles]

        for role, claimtime in sorted(
            config['roles'].items(), key=lambda r: member._roles.index(int(r[0])) if int(r[0]) in member._roles else -1
        ):
            if int(role) in roles:
                if not claimtime['override']:
                    base += claimtime['time']
                else:
                    base = claimtime['time']

        if not base:
            return None
        return base

    def get_win_message(self, guild_id: int, /) -> str | None:
        """Gets a ``guild_id``'s win message.

        Parameters
        ----------
        guild_id: :class:`int`
            The guild ID.

        Returns
        -------
        Optional[:class:`str`]
            The win message, or ``None``.
        """

        config = self.get(guild_id)

        if config is None or not config["winmsg_enabled"]:
            return None
        return config['win_message']

    async def create_claimtime(self, role: discord.Role, time: float, override: bool = False) -> None:
        """Creates a claimtime for a role.

        Parameters
        ----------
        role: :class:`discord.Role`
            The role to add the claimtime to.
        time: :class:`float`
            The claim time.
        override: :class:`bool`
            Whether the role should override other claimtimes.
        """

        guild = self.get(role.guild.id)
        if guild is None:
            guild = {'roles': {str(role.id): {'duration': time, 'override': override}}, 'winmsg': None}

        await self.set(role.guild.id, guild)

    async def delete_claimtime(self, role: discord.Role) -> None:
        """Deletes a claimtime for a role.

        Parameters
        ----------
        role: :class:`discord.Role`
            The role to delete from the claimtime.
        """

        guild = self.get(role.guild.id)
        if guild is None:
            return

        guild["roles"].pop(role.id, None)
        await self.set(role.guild.id, guild)
