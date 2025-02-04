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

from typing import Literal, TypeVar, Any

Key = TypeVar("Key", object, str)


class _MissingSentinel:
    """Missing sentinel to represent non-recognized objects"""

    __slots__ = ()
    __eq__ = __ne__ = __bool__ = lambda self, *_: False
    __int__ = __hash__ = lambda self: 0
    __str__ = __repr__ = lambda self: "..."


class MentionableMissing(_MissingSentinel):
    __slots__ = ("id", "type")

    def __init__(
        self, id: int | None, type: Literal["channel", "user", "role", "missing"]
    ) -> None:
        self.id = id
        self.type = type

    @property
    def mention(self) -> str:
        if self.type == "channel":
            return f"<#{self.id}>"
        elif self.type == "user":
            return f"<@{self.id}>"
        elif self.type == "role":
            return f"<@&{self.id}>"
        elif self.type == "missing":
            return "Sin establecer"
        return "<#0>"


MISSING: Any = _MissingSentinel()
