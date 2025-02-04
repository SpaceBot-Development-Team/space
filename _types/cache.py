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

import enum
import time
import asyncio

from functools import wraps
from typing import Any, ParamSpec, TypeVar, Protocol
from collections.abc import Callable, Coroutine, MutableMapping

from lru import LRU

R = TypeVar('R')
P = ParamSpec('P')

__all__ = ('cache',)

class CacheProtocol(Protocol[R, P]):
    cache: MutableMapping[str, asyncio.Task[R]]

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> asyncio.Task[R]:
        ...

    def get_key(self, *args: P.args, **kwargs: P.kwargs) -> str:
        ...

    def invalidate(self, *args: P.args, **kwargs: P.kwargs) -> bool:
        ...

    def invalidate_containing(self, key: str) -> None:
        ...

    def get_stats(self) -> tuple[int, int]:
        ...


class ExpiringCache(dict):
    def __init__(self, seconds: float) -> None:
        self.__ttl: float = seconds
        super().__init__()

    def __verify_integrity(self) -> None:
        current_time = time.monotonic()
        to_remove = [k for (k, (v, t)) in super().items() if current_time > (t + self.__ttl)]
        for k in to_remove:
            del self[k]

    def __contains__(self, key: object) -> bool:
        self.__verify_integrity()
        return super().__contains__(key)

    def __getitem__(self, key: object):
        self.__verify_integrity()
        v, _ = super().__getitem__(key)
        return v

    def get(self, key: object, default: Any | None = None):
        v = super().get(key, default)
        if v is default:
            return default
        return v[0]

    def __setitem__(self, key: object, value: Any):
        super().__setitem__(key, (value, time.monotonic()))

    def values(self):  # type: ignore
        return map(lambda x: x[0], super().values())

    def items(self):  # type: ignore
        return map(lambda x: (x[0], x[1][0]), super().items())


class Strategy(enum.Enum):
    lru = 1
    raw = 2
    timed = 3


def cache(
    *,
    max_size: int = 128,
    strategy: Strategy = Strategy.lru,
    ignore_kwargs: bool = False,
) -> Callable[[Callable[P, Coroutine[Any, Any, R]]], CacheProtocol[R, P]]:
    def decorator(func: Callable[P, Coroutine[Any, Any, R]]) -> CacheProtocol[R, P]:
        if strategy is Strategy.lru:
            _internal_cache = LRU(max_size)
            _stats = _internal_cache.get_stats
        elif strategy is Strategy.raw:
            _internal_cache = {}
            _stats = lambda: (0, 0)
        elif strategy is Strategy.timed:
            _internal_cache = ExpiringCache(max_size)
            _stats = lambda: (0, 0)

        def _make_key(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
            def _true_repr(o):
                if o.__class__.__repr__ is object.__repr__:
                    return f'<{o.__class__.__module__}.{o.__class__.__name__}>'
                return repr(o)

            key = [f'{func.__module__}.{func.__name__}']
            key.extend(_true_repr(o) for o in args)
            if not ignore_kwargs:
                for k, v in kwargs.items():
                    key.append(_true_repr(k))
                    key.append(_true_repr(v))

            return ':'.join(key)

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> asyncio.Task[R]:
            key = _make_key(args, kwargs)
            try:
                task = _internal_cache[key]
            except KeyError:
                _internal_cache[key] = task = asyncio.create_task(func(*args, **kwargs))
                return task
            else:
                return task

        def _invalidate(*args: P.args, **kwargs: P.kwargs) -> bool:
            try:
                del _internal_cache[_make_key(args, kwargs)]
            except KeyError:
                return False
            return True

        def _invalidate_containing(key: str) -> None:
            to_remove = []
            for k in _internal_cache.keys():
                if key in k:
                    to_remove.append(k)
            for k in to_remove:
                try:
                    del _internal_cache[k]
                except KeyError:
                    continue

        wrapper.cache = _internal_cache  # type: ignore
        wrapper.get_key = lambda *args, **kwargs: _make_key(args, kwargs)  # type: ignore
        wrapper.invalidate = _invalidate  # type: ignore
        wrapper.get_stats = _stats  # type: ignore
        wrapper.invalidate_containing = _invalidate_containing  # type: ignore
        return wrapper  # type: ignore
    return decorator
