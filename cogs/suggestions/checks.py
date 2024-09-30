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

from typing import TYPE_CHECKING, Literal

from discord.ext import commands
from discord.ext.commands._types import Check

from _types.errors import SuggestionsNotEnabled
from .utils import get_config

if TYPE_CHECKING:
    from ..._types.context import SuggestionsContext as Context

__all__ = ("suggestions_enabled", "ensure_config")


def suggestions_enabled() -> Check[Context]:
    """Checks that suggestions are enabled"""

    async def decorator(ctx: Context) -> bool:
        config = await get_config(ctx)  # type: ignore
        ctx.config = config

        if not config.enabled:
            raise SuggestionsNotEnabled()

        return True

    return commands.check(decorator)


def ensure_config() -> Check[Context]:
    """Ensures that a config is created"""

    async def decorator(ctx: Context) -> Literal[True]:
        config = await get_config(ctx)  # type: ignore
        ctx.config = config
        return True

    return commands.check(decorator)
