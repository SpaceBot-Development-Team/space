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

import asyncio
from collections import deque, OrderedDict
from typing import Generic, TypeVar

K = TypeVar('K')
V = TypeVar('V')

__all__ = ('Queue',)


class Queue(Generic[K, V]):
    def __init__(self) -> None:
        self._futs: deque[asyncio.Future[None]] = deque()
        self._d: OrderedDict[K, V] = OrderedDict()
        self._loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

    def _awake(self) -> None:
        while self._futs:
            fut = self._futs.popleft()
            if not fut.done():
                fut.set_result(None)
                break

    def __repr__(self) -> str:
        return f'<Queue data={self._d!r} getters[{len(self._futs)}]>'

    def __len__(self) -> int:
        return len(self._d)

    def is_empty(self) -> bool:
        return not self._d

    def put(self, key: K, value: V) -> None:
        self._d[key] = value
        self._awake()

    async def get(self) -> V:
        while self.is_empty():
            getter = self._loop.create_future()
            self._futs.append(getter)

            try:
                await getter
            except:
                getter.cancel()
                try:
                    self._futs.remove(getter)
                except ValueError:
                    pass

                if not self.is_empty() and not getter.cancelled():
                    self._awake()
                raise

        _, v = self._d.popitem(last=False)
        return v

    def pending(self, key: K) -> bool:
        return key in self._d

    def cancel(self, key: K) -> V | None:
        return self._d.pop(key, None)

    def clear(self) -> None:
        self._d.clear()
