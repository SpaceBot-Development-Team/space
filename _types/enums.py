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

# This copies the try_enum function from @Rapptz/discord.py discord/enums.py file
# so the code does not break if any changes in that function or related are made.

from typing import Any, TypeVar

from discord.enums import Enum

E = TypeVar('E', bound=Enum)

def create_unknown_value(cls: type[E], value: Any) -> E:
    value_cls = cls._enum_value_cls_  # type: ignore
    name = f'unknown_{value}'
    return value_cls(name=name, value=value)

def try_enum(cls: type[E], value: Any) -> E:
    try:
        return cls._enum_value_map_[value]  # type: ignore
    except (KeyError, TypeError, AttributeError):
        return create_unknown_value(cls, value)
