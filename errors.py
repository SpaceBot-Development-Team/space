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

from discord.ext import commands

__all__ = (
    'BadDuration',
    'BadWinnersArgument',
)


class BadDuration(commands.BadArgument):
    """Error raised on any giveaway-related command that indicates a duration
    is not valid.
    """

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__()


class BadWinnersArgument(commands.BadArgument):
    """Error raised when, in a giveaway, a bad winners amount is provided."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__()


class NoGiveawayPrivileges(commands.CheckFailure):
    """Error raised when, creating, rerolling or anything related to giveaways,
    the author does not have the manager role nor manage_guild permissions.
    """

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__()


class ModuleDisabled(commands.CommandError):
    def __init__(self, module: str) -> None:
        super().__init__(f'Module `{module}` is disabled!')
