from __future__ import annotations

import discord

from typing import Literal, TypeVar, Type, Any

Key = TypeVar("Key", object, str)


class _MissingSentinel:
    """Missing sentinel to represent non-recognised objects"""

    __slots__ = ()
    __eq__ = __ne__ = __bool__ = lambda *_: False
    __int__ = __hash__ = lambda: 0
    __str__ = __repr__ = lambda: "..."

    def __getitem__(self, key: Type[Key]) -> Key:
        if key == type(discord.Role):
            self.id: int = 0
            self.mention: str = "Ninguno"


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
