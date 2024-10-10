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

from typing import TypeVar

from discord import Interaction, DMChannel, GroupChannel, Guild, Member, User, Client
from discord.abc import GuildChannel

__all__ = (
    "DMInteraction",
    "PrivateChannelInteraction",
    "GuildInteraction",
)

# fmt: off

# We use a different typevar per each class as using the same could make the
# type checker go crazy on some machines.
D = TypeVar('D', bound='Client')
P = TypeVar('P', bound='Client')
G = TypeVar('G', bound='Client')

class DMInteraction(Interaction[D]):
    guild: None
    guild_id: None
    guild_locale: None
    channel: DMChannel
    user: User


class PrivateChannelInteraction(Interaction[P]):
    guild: None
    channel: GroupChannel
    user: User


class GuildInteraction(Interaction[G]):
    guild: Guild
    guild_id: int
    channel: GuildChannel
    user: Member

# fmt: on
