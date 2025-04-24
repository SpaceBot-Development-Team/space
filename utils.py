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

import datetime

import discord
from discord.ext import commands

__slots__ = (
    'format_dt',
)


def format_td(td: datetime.timedelta) -> str:
    fmts = []

    total = round(td.total_seconds())
    days, r = divmod(total, 86400)
    hours, r = divmod(r, 3600)
    minutes, seconds = divmod(r, 60)

    if days:
        fmts.append(
            f'{days} day{"s" if days != 1 else ""}',
        )
    if hours:
        fmts.append(
            f'{hours} hour{"s" if hours != 1 else ""}',
        )
    if minutes:
        fmts.append(
            f'{minutes} minute{"s" if minutes != 1 else ""}',
        )
    if seconds or not fmts:
        fmts.append(
            f'{seconds} second{"s" if seconds != 1 else ""}',
        )
    return discord.utils._human_join(
        fmts, final='and',
    )


@discord.utils.copy_doc(commands.has_guild_permissions)
def has_permissions(**perms: bool):
    def decorator(cmd):
        commands.check_any(commands.has_guild_permissions(**perms), commands.is_owner())(cmd)
        discord.app_commands.default_permissions(**perms)(cmd)
        return cmd
    return decorator
