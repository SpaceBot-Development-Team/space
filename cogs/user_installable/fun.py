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

from functools import partial
import io

import random

import urllib.parse

from typing import ClassVar, Literal, TypeAlias, Union

import discord
import discord.ext.commands
from discord import app_commands as commands

from _types import Bot


User: TypeAlias = Union[discord.User, discord.Member]


@commands.allowed_installs(guilds=False, users=True)
@commands.allowed_contexts(guilds=True, private_channels=True, dms=True)
class Fun(discord.ext.commands.GroupCog, name="fun"):
    """Comandos de diversión"""

    BASE_JEYY_URL: ClassVar[str] = "https://api.jeyy.xyz/v2"

    def __init__(self, bot: Bot) -> None:
        self.bot: Bot = bot
        self._request_headers: dict[str, str] = {
            "Authorization": "Bearer " + bot.get_token("Jeyy"),
            "accept": "application/json",
        }
        self._parser = urllib.parse.quote
        self.session_get = partial(self.bot.session.get, headers=self._request_headers)

    @staticmethod
    def _convert_bytes_to_io(base: bytes) -> io.BytesIO:
        buffer = io.BytesIO(base)
        buffer.seek(0)
        return buffer

    async def convert_bytes_to_io(self, base: bytes) -> io.BytesIO:
        loop = self.bot.loop
        fut = await loop.run_in_executor(None, self._convert_bytes_to_io, base)
        return fut

    async def get_pet_pet(self, image_url: str) -> discord.File:
        async with self.bot.session.get(
            self.BASE_JEYY_URL + f"/image/patpat?image_url={self._parser(image_url)}",
            headers=self._request_headers,
        ) as response:
            stream = await response.read()
            file_buffer = await self.convert_bytes_to_io(stream)
            return discord.File(file_buffer, filename="petpet.gif")

    async def get_abstract_image(self, image_url: str) -> discord.File:
        async with self.session_get(
            self.BASE_JEYY_URL + "/image/abstract",
            params={"image_url": self._parser(image_url)},
        ) as resp:
            stream = await resp.read()
            file_buffer = await self.convert_bytes_to_io(stream)
            return discord.File(file_buffer, filename="abstract.gif")

    async def get_ace(
        self, name: str, side: Literal["attorney", "prosecutor"], text: str
    ) -> discord.File:
        async with self.session_get(
            self.BASE_JEYY_URL + "/image/ace",
            params={
                "name": name,
                "side": side,
                "text": text,
            },
        ) as resp:
            stream = await resp.read()
            file_buffer = await self.convert_bytes_to_io(stream)
            return discord.File(file_buffer, filename="ace.gif")

    async def get_bomb(self, image_url: str) -> discord.File:
        async with self.session_get(
            self.BASE_JEYY_URL + "/image/bomb",
            params={"image_url": self._parser(image_url)},
        ) as resp:
            stream = await resp.read()
            buffer = await self.convert_bytes_to_io(stream)
            return discord.File(buffer, filename="bomb.gif")

    async def get_cow(self, image_url: str) -> discord.File:
        async with self.session_get(
            self.BASE_JEYY_URL + "/image/cow",
            params={"image_url": self._parser(image_url)},
        ) as resp:
            stream = await resp.read()
            buffer = await self.convert_bytes_to_io(stream)
            return discord.File(buffer, filename="cow.gif")

    @commands.command(name="petpet")
    @commands.checks.cooldown(1, 10, key=lambda i: (i.guild_id, i.user.id))
    @commands.describe(user="El usuario del que crear el GIF")
    async def image_petpet(self, itx: discord.Interaction, *, user: User) -> None:
        """Crea un GIF de PetPet del usuario."""
        await itx.response.defer()
        avatar = user.display_avatar
        file = await self.get_pet_pet(avatar.url)
        await itx.followup.send(file=file)

    @commands.command(name="abstract")
    @commands.checks.cooldown(1, 10, key=lambda i: (i.guild_id, i.user.id))
    @commands.describe(user="El usuario del que crear el GIF")
    async def image_abstract(self, itx: discord.Interaction, *, user: User) -> None:
        """Crea un GIF abstracto del usuario."""
        await itx.response.defer()
        avatar = user.display_avatar
        file = await self.get_abstract_image(avatar.url)
        await itx.followup.send(file=file)

    @commands.command(name="ace")
    @commands.checks.cooldown(1, 10, key=lambda i: (i.guild_id, i.user.id))
    @commands.describe(
        name="El nombre que usar en el ace",
        side="El lugar en el que se encuentra el personaje",
        text="El texto que mostrar",
    )
    @commands.choices(
        side=[
            commands.Choice(name="Abogado", value="attorney"),
            commands.Choice(name="Fiscal", value="prosecutor"),
        ],
    )
    async def image_ace(
        self, itx: discord.Interaction, name: str, side: commands.Choice[str], text: str
    ) -> None:
        """Crea un GIF de Ace Attorney"""
        await itx.response.defer()
        file = await self.get_ace(name, side.value, text)  # type: ignore
        await itx.followup.send(file=file)

    @commands.command(name="bomb")
    @commands.checks.cooldown(1, 10, key=lambda i: (i.guild_id, i.user.id))
    @commands.describe(user="El usuario que explotará")
    async def image_bomb(self, itx: discord.Interaction, *, user: User) -> None:
        """Crea un GIF de un usuario explotando."""
        await itx.response.defer()
        avatar = user.display_avatar
        file = await self.get_bomb(avatar.url)
        await itx.followup.send(file=file)

    @commands.command(name="cow")
    @commands.checks.cooldown(1, 10, key=lambda i: (i.guild_id, i.user.id))
    @commands.describe(user="El usuario que convertir en una vaca")
    async def image_cow(self, itx: discord.Interaction, *, user: User) -> None:
        """Crea un GIF de un usuario convertido en vaca giratoria."""
        await itx.response.defer()
        avatar = user.display_avatar
        file = await self.get_cow(avatar.url)
        await itx.followup.send(file=file)
