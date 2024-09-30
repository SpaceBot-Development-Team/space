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

import copy
import asyncio
from typing import TYPE_CHECKING, Any, List

import discord

if TYPE_CHECKING:
    from typing_extensions import Self

    from ..._types import Context

MISSING = discord.utils.MISSING
human_join = discord.utils._human_join


class StartAnyways(discord.ui.View):
    """Represents a start abtwats vuew,

    Parameters
    ----------
    game: :class:`TypeRace`
        The game.
    """

    def __init__(self, game: TypeRace, /) -> None:
        self.game: TypeRace = game
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Comenzar",
        style=discord.ButtonStyle.green,
    )
    async def start_game(
        self, interaction: discord.Interaction, button: discord.ui.Button[StartAnyways]
    ) -> None:
        """Starts the game"""
        self.start_game.disabled = True
        await interaction.response.edit_message(
            content="Comenzando juego...", view=self
        )

        await self.game.start()


class LFPView(discord.ui.View):
    """Represents a looking-for-players view.

    Parameters
    ----------
    game: :class:`TypeRace`
        The game.
    """

    def __init__(self, game: TypeRace, /) -> None:
        self.game: TypeRace = game
        super().__init__(timeout=None)

        # using the absolute timeout hack
        # (thanks Danny for the snippet ♥)

        self._still_timeout: bool = True
        self.loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        self.loop.call_later(60 * 5, callback=self.abs_tmout)

    def abs_tmout(self) -> None:
        """The absoulte timeout thing."""

        if not self._still_timeout:
            return

        self.loop.create_task(self.on_timeout, name="timeout view")  # type: ignore
        self.stop()

    @discord.ui.button(
        label="Unirse",
        emoji=discord.PartialEmoji.from_str("<:icon_thumbs_up:1249377442116796497>"),
        style=discord.ButtonStyle.primary,
        row=0,
    )
    async def join_game(
        self, interaction: discord.Interaction, button: discord.ui.Button[LFPView]
    ) -> None:
        """Joins the game"""

        if interaction.user in self.game:
            self.game.remove_player(interaction.user.id)
            await self.game.update_message(interaction)

        else:
            self.game.add_player(interaction.user)
            await self.game.update_message(interaction)

    @discord.ui.button(
        label="Comenzar",
        emoji=discord.PartialEmoji.from_str("<:verified:1249742461757161576>"),
        style=discord.ButtonStyle.success,
        row=0,
    )
    async def start_game(
        self, interaction: discord.Interaction, button: discord.ui.Button[LFPView]
    ) -> None:
        """Starts the game"""

        if self.game.should_start():
            await self.game.start()
        else:
            await interaction.response.send_message(
                f"Solo sois {len(self.game.players)}, ¿seguro que quieres comenzar?",
                view=StartAnyways(self.game),
                ephemeral=True,
            )


class TypeRace:
    """Represents a type race game.

    Parameters
    ----------
    ctx: :class:`discord.ext.commands.Context`
        The context to use with this game.
    players: List[:class:`discord.Member`]
        The list of players that are going to play this type-racer game.
    message: :class:`discord.Message`
        The message that will be used for the edits (autoset if no value is passed).
    """

    def __init__(
        self,
        ctx: Context,
        players: List[discord.Member],
        /,
        *,
        message: discord.Message = MISSING,
    ) -> None:
        self.ctx: Context = ctx
        if any(player.bot for player in players):
            raise ValueError("One of the players is a bot, please try again")

        self.players: List[discord.Member] = players
        self._message: discord.Message = message

    def __contains__(self, value: Any) -> bool:
        if isinstance(value, (discord.Member, discord.User)):
            return self.player_exists(value.id)

        return value in self.players

    def player_exists(self, id: int, /) -> bool:
        """:class:`bool`: Returns ``True`` if the player is currently playing."""
        return discord.utils.get(self.players, id=id) is not None

    def should_start(self) -> bool:
        """:class:`bool`: Returns whether it is recommended to start the game
        or not.
        """
        return len(self.players) >= 3

    def add_player(self, member: discord.Member, /) -> Self:
        """Adds a player to the list.

        This returns itself to allow fluent chaining style.

        Parameters
        ----------
        member: :class:`discord.Member`
            The member to add to the player list.

        Raises
        ------
        ValueError
            The member is a bot.

        Returns
        -------
        :class:`TypeRace`
            This game.
        """

        if member.bot:
            raise ValueError("Member if a bot, and therefore cant't play")

        self.players.append(member)

        return self

    def remove_player(self, id: int, /) -> None:
        """Removes a player from the list.

        If not found just ignores.

        Parameters
        ----------
        id: :class:`int`
            The member ID of the player to remove.
        """

        new: List[discord.Member] = []

        for m in self.players:
            if m.id != id:
                new.append(m)

        self.players = new
        del new

    async def looking_for_players(self) -> List[discord.Member]:
        """Creates a view that asks for participants.

        This creates a message, and a view, then waits for it to stop
        and when that is done, returns the player list (although it updates
        :attr:`players`).

        Returns
        -------
        List[:class:`discord.Member`]
            The participants.
        """

        view = LFPView(self)

        if self._message is MISSING:
            self._message = await self.ctx.send(
                f"¡{self.ctx.author.mention} está buscando contrincantes para jugar a Type-Race!",
                embed=discord.Embed(
                    title="Participantes actuales:",
                    description=human_join(
                        tuple(p.mention for p in self.players),
                        final="y",
                    ),
                    color=self.ctx.bot.default_color,
                ),
                view=view,
            )
        else:
            self._message = await self._message.edit(
                content=f"¡{self.ctx.author.mention} está buscando contrincantes para jugar a Type-Race!",
                embed=discord.Embed(
                    title="Participantes actuales:",
                    description=human_join(
                        tuple(p.mention for p in self.players),
                        final="y",
                    ),
                    color=self.ctx.bot.default_color,
                ),
                view=view,
            )

        await view.wait()
        return self.players

    async def start(self) -> None:
        """Starts this game.

        This does the following:

        - Send a message with a view asking for participants.
        - Edit that message, add a timer (timestamp) for a countdown.
        - Edit that message with the word.
        """

        players = await self.looking_for_players()
