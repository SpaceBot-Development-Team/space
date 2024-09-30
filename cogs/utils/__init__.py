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

from typing import Callable, List, Optional, Tuple, TypeVar, Sequence

import discord

from . import paginator

__all__ = (
    "paginator",
    "pair",
)

A = TypeVar("A")
B = TypeVar("B")


def pair(
    a: Sequence[A],
    b: Sequence[B],
    *,
    key: Optional[Callable[[A, B], bool]] = None,
    strict: bool = False,
) -> List[Tuple[A, Optional[B]]]:
    """Returns pairs of tuples (c, d) from iterables a and b.

    This iterates through ``a`` and finds any coincidence using ``key``, ``d`` could
    be ``None`` if no coincidence is found.

    ``key`` is called until one is true, then, it appends it to the result.
    If it is ``None`` this is just a ``zip(a, b)``.

    ``strict`` represents whether to raise an error if ``d`` is ``None``. ``False`` by
    default.
    """

    if key is None:
        return list(zip(a, b))

    def solved_key(c: A) -> Callable[[B], bool]:
        def inner(d: B) -> bool:
            return key(c, d)

        return inner

    ret: List[Tuple[A, Optional[B]]] = []

    for c in a:
        d: Optional[B] = discord.utils.find(solved_key(c), b)
        if strict is True and d is None:
            raise ValueError(f"Could not find a pair for {c}")
        ret.append((c, d))
    return ret
