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

import inspect
from typing import Dict, Any, List, Optional, TypeVar, Callable, TYPE_CHECKING, Union

import asyncio
from discord.utils import maybe_coroutine, MISSING, copy_doc
from discord import app_commands
from discord.ext import commands as ext_commands

if TYPE_CHECKING:
    from typing_extensions import Self

    from _types.bot import Bot

T = TypeVar("T", bound=Callable[..., Any])

__all__ = ("ContextMenuHolder", "context_menu")


class ContextMenuHolder:
    """Represents a context menu holder.

    A context menu holder allows context menus to be categorised in cogs
    without raising errors.

    Parameters
    ----------
    bot: Optional[:class:`commands.Bot`]
        The bot that this context menu holder belongs to, this can be missing
        for partially initialized context menu holders.

    Attributes
    ----------
    bot: Optional[:class:`commands.Bot`]
        The bot attached to this context menu holder, or ``None``.
    """

    def __init__(self, bot: Optional[Bot]):
        self.bot: Optional[Bot] = bot
        self._commands: List[app_commands.ContextMenu] = []
        self.__background_attach_task__: Optional[asyncio.Task[None]] = None

    @property
    def commands(self) -> List[app_commands.ContextMenu]:
        """List[:class:`app_commands.ContextMenu`]: The commands the current holder contains."""
        return self._commands.copy()

    def can_be_added(self) -> bool:
        """:class:`bool`: Returns ``True`` if the current holder can be added to the command
        tree.
        """
        return self.bot is not None

    @classmethod
    def partial_holder(cls) -> Self:
        """Creates a partial context menu holder without a bot attached to it.

        Returns
        -------
        :class:`ContextMenuHolder`
            The partially initialised context menu holder.
        """
        return cls(None)

    def add_command(self, command: app_commands.ContextMenu) -> Self:
        """Adds a command to the holder.

        Parameters
        ----------
        command: :class:`app_commands.ContextMenu`
            The context menu to add to the holder.

        Returns
        -------
        :class:`ContextMenuHolder`
            The updated context menu holder. This allows fluent-style
            chaining.
        """
        self._commands.append(command)
        return self

    def remove_command(self, command: app_commands.ContextMenu) -> None:
        """Removes a command from the holder.

        .. note::

            This **does not** remove it from the command tree.

        Parameters
        ----------
        command: :class:`app_commands.ContextMenu`
            The command to remove from the holder.
        """

        self._commands.remove(command)

    def copy_to_tree(self) -> None:
        """Adds all the context menus to the command tree.

        Raises
        ------
        ValueError
            This context menu holder is partial and therefor cannot
            add commands to a command tree.
        """

        if not self.can_be_added():
            raise ValueError(
                "This context menu holder is partial and therefor cannot add commands to a command tree"
            )

        for command in self._commands:
            self.bot.tree.add_command(command)  # type: ignore

    def attach(self, bot: Bot) -> None:
        """Attaches this context menu holder to a bot.

        Parameters
        ----------
        bot: :class:`commands.Bot`
            The bot to attach this context menu holder to.
        """
        self.bot = bot

        loop = asyncio.get_running_loop()
        self.__background_attach_task__ = loop.create_task(
            maybe_coroutine(self.on_attach)
        )

    def on_attach(self) -> None:
        """Event called when the context menu holder gets attached to a
        bot.

        This can be a :py:`coroutine <ref coroutines>`
        """

    def load_commands_from(self, cog: ext_commands.Cog) -> None:
        """Loads the commands from a cog.

        Parameters
        ----------
        cog: :class:`commands.Cog`
            The cog to load the commands.
        """
        for _, member in inspect.getmembers(cog):
            if getattr(member, "__cog_context_menu__", False):
                menu = app_commands.ContextMenu(
                    **getattr(member, "__cog_context_menu_kwargs__"),
                    callback=member,
                )
                self._commands.append(menu)


@copy_doc(app_commands.context_menu)
def context_menu(
    *,
    name: Union[str, app_commands.locale_str] = MISSING,
    nsfw: bool = False,
    auto_locale_strings: bool = True,
    extras: Dict[Any, Any] = MISSING,
) -> Callable[[T], T]:
    def decorator(func: T) -> T:
        func.__cog_context_menu__ = True  # type: ignore
        func.__cog_context_menu_kwargs__ = {  # type: ignore
            "name": name,
            "nsfw": nsfw,
            "auto_locale_strings": auto_locale_strings,
            "extras": extras,
        }
        return func

    return decorator
