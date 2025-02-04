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

from typing import Any, TypeVar, overload, TYPE_CHECKING
from collections.abc import Callable

import discord
from discord.ext.commands.flags import FlagConverter, flag
from discord.ext.commands.converter import RoleConverter


class AddStockFlags(FlagConverter):
    category: str = flag(
        name="category",
        aliases=["cat"],
        description="La categoría a la que añadir el stock",
        default="Default",
    )
    stock: str = flag(name="stock", description="El stock que añadir")


class GuildSafetyFlags(FlagConverter):
    timedout: bool = flag(name="timedout", aliases=["out", "to"], default=True)
    unusual_dms: bool = flag(
        name="unusal-dms", aliases=["dms", "unusual-dm"], default=True
    )
    roles: tuple = flag(converter=RoleConverter, aliases=["role"], default=tuple())
    users: tuple = flag(converter=RoleConverter, aliases=["user"], default=tuple())


class RemoveVouchFlags(FlagConverter, prefix="--", delimiter=" "):
    user: discord.Member = flag(positional=True, name="user")
    remove_recent: bool = flag(aliases=["rr"], default=True)


## Bare copy from discord.py flags

if TYPE_CHECKING:
    from discord.flags import BaseFlags, flag_value, alias_flag_value

else:
    T = TypeVar('T', bound='BaseFlags')

    class BaseFlags:
        __slots__ = ('value',)

        def __init__(self, value: int = 0, **kwargs: bool) -> None:
            self.value: int = value
            for kw, v in kwargs.items():
                if not hasattr(self, kw):
                    raise TypeError(f'Invalid flag provided for {self.__class__.__name__}: {kw!r}')
                setattr(self, kw, v)

        @classmethod
        def _from_value(cls, value: int):
            return cls(value)

        def __eq__(self, other: object) -> bool:
            return isinstance(other, self.__class__) and self.value == other.value

        def __hash__(self) -> int:
            return hash(self.value)

        def __repr__(self) -> str:
            return f'<{self.__class__.__name__} value={self.value}>'

        def is_empty(self) -> bool:
            """:class:`bool`: Returns ``True`` if the flags have a falsey value."""
            return self.value == 0

        def _has_flag(self, f: int) -> bool:
            return (self.value & f) == f

        def _set_flag(self, f: int, v: bool) -> None:
            if v is True:
                self.value |= f
            elif v is False:
                self.value &= ~f
            else:
                raise TypeError(f'Value set for {self.__class__.__name__} must be a bool.')

    class flag_value:
        def __init__(self, func: Callable[[Any], int]) -> None:
            self.flag: int = func(None)
            self.__doc__: str | None = func.__doc__

        @overload
        def __get__(self, instance: None, owner: type[Any]):
            ...

        @overload
        def __get__(self, instance: T, owner: type[T]) -> bool:
            ...

        def __get__(self, instance: T | None, owner: type[T]) -> Any:
            if instance is None:
                return self
            return instance._has_flag(self.flag)

    class alias_flag_value(flag_value):
        pass
