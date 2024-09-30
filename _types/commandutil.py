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

from typing import TYPE_CHECKING, Callable, List, Sequence, TypeVar

from discord import app_commands
from discord.ext import commands
from discord.ext.commands._types import Check

from models import Guild, WarnsConfig

if TYPE_CHECKING:
    from .context import GuildContext

FI = TypeVar("FI")


def can_run_strike() -> Check[GuildContext]:
    async def pred(ctx: GuildContext) -> bool:
        if not ctx.guild:
            raise commands.NoPrivateMessage(
                "Este comando no se puede utilizar en (G)DMs"
            )
        if not await Guild.exists(id=ctx.guild.id):
            return False

        config = await Guild.get(id=ctx.guild.id)
        return config.staff_report is not None and config.user_report is not None

    return commands.check(pred)


def can_run_warn() -> Check[GuildContext]:
    async def pred(ctx: GuildContext) -> bool:
        if not ctx.guild:
            raise commands.NoPrivateMessage(
                "Este comando no se puede utilizar en (G)DMs"
            )
        if not await WarnsConfig.exists(id=ctx.guild.id):
            return False

        config = await WarnsConfig.get(id=ctx.guild.id)
        return config.enabled

    return commands.check(pred)


def has_permissions(**perms: bool):
    """Adds a ``app_commands.default_permissions`` and ``commands.has_permissions`` checls
    at once.
    """

    def decorator(func):
        commands.has_permissions(**perms)(func)
        app_commands.default_permissions(**perms)(func)
        return func

    return decorator


def find_all(predicate: Callable[[FI], bool], iterable: Sequence[FI]) -> List[FI]:
    """Iterates over ``iterable`` and returns all values that make ``predicate(value)`` return a truthy value.

    Unlike ``discord.utils.find``, this returns various items instead of the first one that meets it.
    """
    return [o for o in iterable if predicate(o)]
