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

import discord
from discord import app_commands
from discord.ext import commands

from models import Suggestion
from _types import group
from .checks import ensure_config
from .utils import get_config
from .views import SuggestionView, ReviewSuggestionView

if TYPE_CHECKING:
    from ..._types.bot import Bot
    from ..._types.context import SuggestionsContext as Context

__all__ = ("Sugerencias",)


class Sugerencias(commands.Cog):
    """Comandos que permiten realizar o configurar sugerencias."""

    def __init__(self, bot: Bot, /) -> None:
        self.bot: Bot = bot
        self.added_persistent_view: bool = False

    async def cog_load(self) -> None:
        self.bot.add_view(SuggestionView(Suggestion))
        self.bot.add_view(ReviewSuggestionView(Suggestion))

    @commands.Cog.listener("on_message")
    async def create_suggestion(self, message: discord.Message) -> None:
        """Event called when a new message is recieved"""
        if message.author.bot:
            return

        self.bot.logger.debug("Suggestion creation on_message dispatched")
        config = await get_config(message)

        if config.enabled is False:
            self.bot.logger.debug(
                "Suggestion discarded as suggestions were not enabled"
            )
            return

        if config.suggestions_channel is None:
            self.bot.logger.debug(
                "Suggestion creation discarded as there was no channel"
            )
            return

        if message.channel.id != config.suggestions_channel:
            self.bot.logger.debug("Suggestion discarded as channel IDs mismatched")
            return

        if config.command_like is True:
            return None  # It invokes the required command
        if config.review_enabled is True:
            if not config.review_channel:
                await message.reply(
                    (
                        "Las revisiones de sugerencias están activas, pero "
                        "no hay un canal establecido. Comunícalo a un administrador."
                    )
                )
                return
            await self.on_suggestion_review_create(message, config)
        else:
            await self.on_suggestion_create(message, config)

    @commands.Cog.listener("on_raw_message_delete")
    async def delete_suggestion(self, payload: discord.RawMessageDeleteEvent) -> None:
        """Event called when a message is deleted"""
        config = await Suggestion.get_or_none(id=payload.message_id)
        if config:
            await config.delete()

    @commands.Cog.listener()
    async def on_suggestion_create(
        self, suggestion: discord.Message, config: SuggestionsConfig
    ) -> None:
        """Event called when a new suggestion is created"""
        self.bot.logger.debug("Suggestion create dispatched")
        view = SuggestionView(Suggestion)
        embed = discord.Embed(color=suggestion.author.color)
        embed.description = suggestion.content
        embed.set_thumbnail(url=suggestion.author.display_avatar.url)
        embed.set_author(name=suggestion.author)
        embed.set_footer(text=f"Author: {suggestion.author.id}")
        updated = view.update_suggestion_embed(embed, type=None)
        channel = self.bot.get_partial_messageable(
            config.suggestions_channel,
            guild_id=suggestion.guild.id,  # type: ignore
            type=discord.ChannelType.text,
        )
        await suggestion.delete()
        message = await channel.send(embed=updated, view=view)
        sgdata = Suggestion(
            id=message.id,
            voted_users=[],
        )
        await sgdata.save()

    @commands.Cog.listener()
    async def on_suggestion_review_create(
        self, suggestion: discord.Message, config: SuggestionsConfig
    ) -> None:
        """Event called when a new suggestion review is created"""
        self.bot.logger.debug("Suggestion review create dispatched")
        await suggestion.delete()
        embed = discord.Embed(color=suggestion.author.color)
        embed.description = suggestion.content
        embed.set_thumbnail(url=suggestion.author.display_avatar.url)
        embed.set_author(name=str(suggestion.author))
        embed.set_footer(text=f"Autor: {suggestion.author.id}")

        view = ReviewSuggestionView(Suggestion)
        view.suggestion_channel = config.suggestions_channel
        channel = self.bot.get_partial_messageable(
            config.review_channel,
            guild_id=suggestion.guild.id,  # type: ignore
            type=discord.ChannelType.text,
        )
        await channel.send(embed=embed, view=view)

    @group(name="suggestions")
    @app_commands.default_permissions(manage_guild=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def suggestions(self, _: Context) -> None:
        """Comandos de gestión de sugerencias"""

    @suggestions.group(name="reviews", fallback="view")
    @commands.has_guild_permissions(manage_guild=True)
    @ensure_config()
    async def sgs_reviews(self, ctx: Context) -> None:
        """Gestionan las revisiones de sugerencias"""
        if not ctx.config.review_channel:
            await ctx.reply("No hay canal de revisión de sugerencias")
        else:
            await ctx.reply(
                f"El canal de revisión de sugerencias es <#{ctx.config.review_channel}>"
            )

    @sgs_reviews.command(name="toggle")
    @commands.has_guild_permissions(manage_guild=True)
    @commands.cooldown(1, 5, commands.BucketType.guild)
    @ensure_config()
    async def sgs_reviews_toggle(self, ctx: Context) -> None:
        """Alterna si se deben revisar las sugerencias antes de enviarlas al feed
        de sugerencias.
        """

        ctx.config.review_enabled = not ctx.config.review_enabled

        if ctx.config.review_enabled is True:
            message = "Se han habilitado las revisiones previas a sugerencias"
        else:
            message = "Se han deshabilitado las revisiones previas a sugerencias"

        await ctx.reply(message)
        await ctx.config.save()

    @sgs_reviews.command(name="set")
    @commands.has_guild_permissions(manage_guild=True)
    @commands.cooldown(1, 5, commands.BucketType.guild)
    @ensure_config()
    @app_commands.describe(
        channel="El canal al que se enviarán las revisiones de sugerencias"
    )
    async def sgs_reviews_channel(
        self,
        ctx: Context,
        *,
        channel: discord.TextChannel,
    ) -> None:
        """Comprueba o establece un canal de revisión de sugerencias."""
        ctx.config.review_channel = channel.id
        await ctx.reply(
            f"Se ha establecido el canal de revisión de sugerencias a {channel.mention}"
        )
        await ctx.config.save()

    @suggestions.group(name="staff", fallback="view")
    @commands.has_guild_permissions(manage_guild=True)
    @ensure_config()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def sgs_staff(self, ctx: Context) -> None:
        """Gestionan el rol de staff de sugerencias"""

        if not ctx.config.staff_role:
            await ctx.reply("No hay rol de staff")
        else:
            await ctx.reply(
                f"El rol de staff actual es <@&{ctx.config.staff_role}>",
                allowed_mentions=discord.AllowedMentions.none(),
            )

    @sgs_staff.command(name="set")
    @commands.has_guild_permissions(manage_guild=True)
    @ensure_config()
    @app_commands.describe(role="El rol de staff")
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def sgs_staff_set(self, ctx: Context, *, role: discord.Role) -> None:
        """Establece el rol de staff. Este rol puede aprobar o denegar sugerencias si las
        revisiones están activadas.
        """
        ctx.config.staff_role = role.id
        await ctx.reply(
            f"Se ha establecido el rol de staff a {role.mention}",
            allowed_mentions=discord.AllowedMentions.none(),
        )
        await ctx.config.save()

    @suggestions.command(name="toggle")
    @ensure_config()
    @commands.has_guild_permissions(manage_guild=True)
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def sgs_toggle(self, ctx: Context) -> None:
        """Alterna si las sugerencias están activadas o no"""
        ctx.config.enabled = not ctx.config.enabled

        if ctx.config.enabled is True:
            message = "Se han habilitado las sugerencias"
        else:
            message = "Se han deshabilitado las sugerencias"
        await ctx.reply(message)
        await ctx.config.save()

    @suggestions.group(name="channel", fallback="view")
    @ensure_config()
    @commands.has_guild_permissions(manage_guild=True)
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def suggestion_channel(self, ctx: Context) -> None:
        """Comprueba el canal de sugerencias actual"""
        if ctx.config.suggestions_channel is None:
            await ctx.reply("No hay canal de sugerencias")
        else:
            await ctx.reply(
                f"El canal de sugerencias es <#{ctx.config.suggestions_channel}>"
            )

    @suggestion_channel.command(name="set")
    @ensure_config()
    @commands.has_guild_permissions(manage_guild=True)
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def sgs_channel_set(
        self, ctx: Context, *, channel: discord.TextChannel
    ) -> None:
        """Establece el canal de sugerencias"""
        ctx.config.suggestions_channel = channel.id
        await ctx.reply(
            f"Se ha establecido el canal de sugerencias a {channel.mention}"
        )
        await ctx.config.save()
