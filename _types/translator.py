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

from typing import TYPE_CHECKING

import aiohttp
import discord
from discord.utils import MISSING
from discord_tools.app_commands import i18n

try:
    import orjson as json
except ImportError:
    import json as json

if TYPE_CHECKING:
    from discord_tools.app_commands.i18n.translator import TranslationLoadStrategy


class Translator(i18n.Translator):
    session: aiohttp.ClientSession
    _translations: dict[discord.Locale, dict[str, dict[str, str]]]  # type: ignore

    def load_translations(  # type: ignore
        self,
        path: str | bytes,
        *,
        strategy: TranslationLoadStrategy = MISSING,
        locale: discord.Locale = MISSING,
    ) -> dict[discord.Locale, dict[str, dict[str, str]]]:  # type: ignore
        data = json.loads(path)
        return self._save_json_data(data)  # type: ignore

    async def load(self) -> None:
        async with self.session.get(
            "https://raw.githubusercontent.com/SpaceBot-Development-Team/translations/refs/heads/master/translations.json",
        ) as resp:
            buffer = await resp.text()
            self.load_translations(buffer, strategy="json")

    async def translate(
        self,
        string: discord.app_commands.locale_str,
        locale: discord.Locale,
        context: discord.app_commands.TranslationContext,
    ) -> str | None:
        data = self._translations.get(locale, {})
        location: discord.app_commands.TranslationContextLocation = context.location
        key = location.name
        sub = data.get(key, {})
        return sub.get(str(string))
