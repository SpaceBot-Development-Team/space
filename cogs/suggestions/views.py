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

from typing import TYPE_CHECKING, Literal, Optional, Type, cast

import discord
from discord import ui

from models import Suggestion

if TYPE_CHECKING:
    from ...models import Suggestion

__all__ = ("SuggestionView", "ReviewSuggestionView")


class SuggestionView(ui.View):
    """Represents the view of a suggestion"""

    def __init__(self, suggestion_cls: Type[Suggestion]) -> None:
        self.suggestions: Type[Suggestion] = suggestion_cls
        super().__init__(timeout=None)

    async def get_config(self, itx: discord.Interaction, /) -> Suggestion:
        """Gets the config of interaction X"""
        config, _ = await Suggestion.get_or_create({"voted_users": []}, id=itx.message.id)  # type: ignore
        return config

    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        return (
            interaction.user.id not in (await self.get_config(interaction)).voted_users
        )

    def update_suggestion_embed(
        self, embed: discord.Embed, /, type: Optional[Literal["u", "n", "d"]]
    ) -> discord.Embed:
        """Updates the embed to append a new vote to X field"""
        new: discord.Embed = embed.copy()
        new.clear_fields()
        fields = embed.fields

        if len(fields) == 0:
            for name in (
                "Votos a favor",
                "Votos nulos",
                "Votos en contra",
            ):
                if (
                    (name == "Votos a favor" and type == "u")
                    or (name == "Votos en contra" and type == "d")
                    or (name == "Votos nulos" and type == "n")
                ):
                    votes = 1
                else:
                    votes = 0
                new.add_field(
                    name=name,
                    value=str(votes),
                    inline=True,
                )
        else:
            for field in fields:
                name: str = cast(str, field.name)
                value: int = int(cast(str, field.value))
                if (
                    (name == "Votos a favor" and type == "u")
                    or (name == "Votos en contra" and type == "d")
                    or (name == "Votos nulos" and type == "n")
                ):
                    value += 1
                new.add_field(
                    name=name,
                    value=str(value),
                    inline=True,
                )
        return new

    @ui.button(
        custom_id="suggestions:upvote",
        emoji=discord.PartialEmoji.from_str("<:tick:1216850806419095654>"),
        row=0,
        style=discord.ButtonStyle.blurple,
    )
    async def upvote(
        self, interaction: discord.Interaction, _: ui.Button[SuggestionView]
    ) -> None:
        """Upvote"""
        message: discord.Message = cast(discord.Message, interaction.message)
        embed: discord.Embed = self.update_suggestion_embed(message.embeds[0], type="u")
        await interaction.response.edit_message(embed=embed)

        config = await self.get_config(interaction)
        config.voted_users.append(interaction.user.id)
        await config.save()

    @ui.button(
        custom_id="suggestions:null",
        emoji=discord.PartialEmoji.from_str("<:null:1216850810982502613>"),
        row=0,
        style=discord.ButtonStyle.gray,
    )
    async def null(
        self, interaction: discord.Interaction, _: ui.Button[SuggestionView]
    ) -> None:
        """Null vote"""
        message: discord.Message = cast(discord.Message, interaction.message)
        embed: discord.Embed = self.update_suggestion_embed(message.embeds[0], type="n")
        await interaction.response.edit_message(embed=embed)

        config = await self.get_config(interaction)
        config.voted_users.append(interaction.user.id)
        await config.save()

    @ui.button(
        custom_id="suggestions:downvote",
        emoji=discord.PartialEmoji.from_str(
            "<:cross:1216850808587554937>",
        ),
        row=0,
        style=discord.ButtonStyle.red,
    )
    async def dwnvote(
        self, interaction: discord.Interaction, _: ui.Button[SuggestionView]
    ) -> None:
        """Downvote"""
        message: discord.Message = cast(discord.Message, interaction.message)
        embed: discord.Embed = self.update_suggestion_embed(message.embeds[0], type="d")
        await interaction.response.edit_message(embed=embed)

        config = await self.get_config(interaction)
        config.voted_users.append(interaction.user.id)
        await config.save()


class ReviewSuggestionView(ui.View):
    """Represents a review suggestion view"""

    def __init__(self, suggestion_cls: Type[Suggestion]) -> None:
        self.suggestion: Type[Suggestion] = suggestion_cls
        self.suggestion_channel: int = discord.utils.MISSING
        super().__init__(timeout=None)

    async def create_suggestion(
        self,
        embed: discord.Embed,
        view: SuggestionView,
        interaction: discord.Interaction,
    ) -> None:
        """Creates the new suggestion model"""
        new = embed.copy()
        embed.add_field(
            name="Aprobada por:",
            value=f'{interaction.user} - {discord.utils.format_dt(discord.utils.utcnow(), style="d")}',
        )
        for child in self.children:
            child.disabled = True  # type: ignore
        await interaction.response.edit_message(embed=embed, view=self)
        channel = interaction.client.get_partial_messageable(
            self.suggestion_channel,
            type=discord.ChannelType.text,
        )
        message = await channel.send(embed=new, view=view)
        config = self.suggestion(id=message.id, voted_users=[])
        await config.save()

    @ui.button(
        label="Aceptar",
        style=discord.ButtonStyle.green,
        custom_id="suggestions:reviews:approve",
        row=0,
        disabled=False,
    )
    async def approve(
        self, interaction: discord.Interaction, _: ui.Button[ReviewSuggestionView]
    ) -> None:
        """Approves the suggestion"""
        view = SuggestionView(self.suggestion)
        embed = interaction.message.embeds[0]  # type: ignore

        await self.create_suggestion(embed, view, interaction)
        self.stop()

    @ui.button(
        label="Rechazar",
        style=discord.ButtonStyle.red,
        custom_id="suggestions:reviews:deny",
        row=0,
        disabled=False,
    )
    async def deny(
        self, interaction: discord.Interaction, _: ui.Button[ReviewSuggestionView]
    ) -> None:
        """Denies the suggestion"""
        embed = interaction.message.embeds[0]  # type: ignore
        embed.color = discord.Color.red()
        embed.add_field(
            name="Rechazada por:",
            value=f'{interaction.user} - {discord.utils.format_dt(discord.utils.utcnow(), style="d")}',
        )

        for child in self.children:
            child.disabled = True  # type: ignore

        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()
