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

from typing import TypedDict, Optional, List


class WarnObject(TypedDict):
    """Represents a warn object

    Parameters
    ----------
    created_at: :class:`str`
        A ISO timestamp that represents the warn creation
    author: :class:`int`
        The ID of the user that gave the warn.
    reason: :class:`str`
        The reason why the warn was created.
    target: :class:`int`
        The target of the warning.
    guild_id: :class:`int`
        The guild ID where this warning happened.
    """

    created_at: str
    author: int
    reason: str
    target: int
    guild_id: int


class WarnRole(TypedDict):
    """Represents a role given when meeting a warn requirement"""

    n: int
    id: int
    role: int
    """The role ID to give when the user meets the requirement"""


class WarnKick(TypedDict):
    """Represents a kick recieved when meeting a warn requirement"""

    n: int
    id: int


class WarnBan(TypedDict):
    """Represents a ban recieved when meeting a warn requirement"""

    n: int
    id: int


class WarnTimeout(TypedDict):
    """Represents a timeout recieved when meeting a warn requirement"""


class WarnMetadata(TypedDict):
    """Represents a metadata dict, all fields are not required as are created by
    updates.
    """

    n: int
    id: int
    duration: float
    """The duration of the timeout"""


class WarnsConfig(TypedDict):
    """Represents the warns config.

    Parameters
    ----------
    roles: List[:class:`WarnRole`]
        A list that contains all the warn roles data.
    timeouts: List[:class:`WarnTimeout`]
        A list that contains all the warn timeouts data.
    kicks: List[:class:`WarnKick`]
        A list that contains all the warn kicks data.
    bans: List[:class:`WarnBan`]
        A list that contains all the warn bans data.
    metadata: Optional[:class:`WarnMetadata`]
        Metadata information, or ``None``.
    """

    roles: List[WarnRole]
    timeouts: List[WarnTimeout]
    kicks: List[WarnKick]
    bans: List[WarnBan]
    metadata: Optional[WarnMetadata]
