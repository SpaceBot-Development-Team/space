"""
The MIT License (MIT)

Copyright (c) 2025-present Developer Anonymous

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

import traceback
import discord
from _types.views import BaseView
from _types.bot import Bot
import wavelink


class NotViewAuthor(discord.app_commands.CheckFailure):
    def __init__(self) -> None:
        super().__init__()


class ManageQueueView(BaseView):
    def __init__(self, author: discord.abc.Snowflake, player: wavelink.Player, embed: discord.Embed) -> None:
        super().__init__(timeout=180)
        self.author: discord.abc.Snowflake = author
        self.player: wavelink.Player = player
        self.embed = embed
        self.message: discord.Message = discord.utils.MISSING

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            raise NotViewAuthor()
        return True

    async def on_error(self, interaction: discord.Interaction[Bot], error: Exception, item: discord.ui.Item, /) -> None:
        if isinstance(error, NotViewAuthor):
            await interaction.response.send_message(
                '¡No puedes utilizar este panel de control!',
                ephemeral=True,
            )
        else:
            interaction.client.logger.error(traceback.format_exception(type(error), error, tb=error.__traceback__))

    def enable_all_children(self) -> None:
        for child in self.children:
            if hasattr(child, 'disabled'):
                child.disabled = False

    @discord.ui.button(emoji='\N{CLOCKWISE RIGHTWARDS AND LEFTWARDS OPEN CIRCLE ARROWS}')
    async def loop_queue(self, interaction: discord.Interaction[Bot], button: discord.ui.Button[ManageQueueView]) -> None:
        self.player.queue.mode = wavelink.QueueMode.loop_all
        self.player.autoplay = wavelink.AutoPlayMode.partial
        self.embed.description = "Modo de reproducción: \N{CLOCKWISE RIGHTWARDS AND LEFTWARDS OPEN CIRCLE ARROWS} Repetir cola de reproducción"
        self.enable_all_children()
        button.disabled = True
        self.shuffle.disabled = False
        await interaction.response.edit_message(embed=self.embed, view=self)

    @discord.ui.button(emoji='\N{CLOCKWISE RIGHTWARDS AND LEFTWARDS OPEN CIRCLE ARROWS WITH CIRCLED ONE OVERLAY}')
    async def loop_single_track(self, interaction: discord.Interaction[Bot], button: discord.ui.Button[ManageQueueView]) -> None:
        if not self.is_premium_interaction(interaction):
            view = self.create_premium_required_view()
            await interaction.response.send_message(
                "Esta función requiere Space Premium, ¡puedes mejorar tu plan actual usando el botón de abajo!",
                view=view,
                ephemeral=True,
            )
            return
        self.player.queue.mode = wavelink.QueueMode.loop
        self.player.autoplay = wavelink.AutoPlayMode.partial
        self.embed.description = "Modo de reproducción: \N{CLOCKWISE RIGHTWARDS AND LEFTWARDS OPEN CIRCLE ARROWS WITH CIRCLED ONE OVERLAY} Canción actual en bucle"
        self.enable_all_children()
        button.disabled = True
        self.shuffle.disabled = True
        await interaction.response.edit_message(embed=self.embed, view=self)

    @discord.ui.button(emoji='\N{TWISTED RIGHTWARDS ARROWS}')
    async def shuffled_queue(self, interaction: discord.Interaction[Bot], button: discord.ui.Button[ManageQueueView]) -> None:
        self.player.queue.shuffle()
        self.player.queue.mode = wavelink.QueueMode.loop_all
        self.player.autoplay = wavelink.AutoPlayMode.partial
        self.embed.description = "Modo de reproducción: \N{TWISTED RIGHTWARDS ARROWS} Aleatorio en la cola de reproducción"
        self.enable_all_children()
        button.disabled = True
        self.shuffle.disabled = False
        await interaction.response.edit_message(embed=self.embed, view=self)

    @discord.ui.button(emoji='\N{CLOCKWISE DOWNWARDS AND UPWARDS OPEN CIRCLE ARROWS}', row=1)
    async def shuffled_with_recommendations(self, interaction: discord.Interaction[Bot], button: discord.ui.Button[ManageQueueView]) -> None:
        if not self.is_premium_interaction(interaction):
            view = self.create_premium_required_view()
            await interaction.response.send_message(
                'Esta función requiere Space Premium, ¡puedes mejorar tu plan actual usando el botón de abajo!',
                view=view,
                ephemeral=True,
            )
            return
        self.player.queue.shuffle()
        self.player.queue.mode = wavelink.QueueMode.loop_all
        self.player.auto_queue.mode = wavelink.QueueMode.loop_all
        self.player.autoplay = wavelink.AutoPlayMode.enabled
        self.embed.description = "Modo de reproducción: \N{CLOCKWISE DOWNWARDS AND UPWARDS OPEN CIRCLE ARROWS} Aleatorio en modo infinito"
        self.enable_all_children()
        button.disabled = True
        self.shuffle.disabled = False
        await interaction.response.edit_message(embed=self.embed, view=self)

    @discord.ui.button(emoji='\N{PERMANENT PAPER SIGN}', row=1)
    async def infinite_queue(self, interaction: discord.Interaction[Bot], button: discord.ui.Button[ManageQueueView]) -> None:
        if not self.is_premium_interaction(interaction):
            view = self.create_premium_required_view()
            await interaction.response.send_message(
                "Esta función requiere Space Premium, ¡puedes mejorar tu plan actual usando el botón de abajo!",
                view=view,
                ephemeral=True,
            )
            return
        self.player.queue.mode = wavelink.QueueMode.loop_all
        self.player.auto_queue.mode = wavelink.QueueMode.loop_all
        self.player.autoplay = wavelink.AutoPlayMode.enabled
        self.embed.description = "Modo de reproducción: \N{PERMANENT PAPER SIGN} Infinito sin aleatorizar"
        self.enable_all_children()
        button.disabled = True
        self.shuffle.disabled = True
        await interaction.response.edit_message(embed=self.embed, view=self)

    @discord.ui.button(emoji='\N{BLACK RIGHT-POINTING TRIANGLE WITH DOUBLE VERTICAL BAR}', row=1)
    async def play_and_stop(self, interaction: discord.Interaction[Bot], button: discord.ui.Button[ManageQueueView]) -> None:
        self.player.queue.mode = wavelink.QueueMode.normal
        self.player.auto_queue.clear()
        self.player.auto_queue.mode = wavelink.QueueMode.normal
        self.player.autoplay = wavelink.AutoPlayMode.disabled
        self.embed.description = "Modo de reproducción: \N{BLACK RIGHT-POINTING TRIANGLE WITH DOUBLE VERTICAL BAR} Reproducir canción actual y pausar"
        self.enable_all_children()
        button.disabled = True
        self.shuffle.disabled = True
        await interaction.response.edit_message(embed=self.embed, view=self)

    @discord.ui.button(label='Mezclar', style=discord.ButtonStyle.blurple)
    async def shuffle(self, interaction: discord.Interaction[Bot], button: discord.ui.Button[ManageQueueView]) -> None:
        self.player.queue.shuffle()
        await interaction.response.edit_message(embed=self.embed, view=self)
