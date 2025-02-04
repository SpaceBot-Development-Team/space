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

from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from _types import GuildContext, group
import wavelink

from .views import ManageQueueView

if TYPE_CHECKING:
    from _types.bot import Bot


class MusicPlayFlags(commands.FlagConverter):
    query: str = commands.flag(positional=True, description="La canción que reproducir, puede ser una URL")
    source: wavelink.TrackSource = commands.flag(description="Donde buscar la canción.", default=wavelink.TrackSource.YouTube)


class Musica(commands.Cog):
    """Comandos relacionados a música."""

    def __init__(self, bot: Bot) -> None:
        self.bot: Bot = bot

    @group(invoke_without_subcommand=False)
    async def music(self, ctx: GuildContext) -> None:
        """Comandos que gestionan el reproductor de música de este servidor."""

    @music.command(
        name="play",
    )
    async def music_play(self, ctx: GuildContext, *, flags: MusicPlayFlags) -> None:
        """Busca y reproduce una canción.
        """

        await ctx.defer()

        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.reply('Necesitas estar en un canal de voz para poder usar este comando.', ephemeral=True)
            return

        player: wavelink.Player | None = ctx.voice_client  # type: ignore

        if player is None:
            player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
            player.autoplay = wavelink.AutoPlayMode.partial
        else:
            if ctx.author.voice.channel.id != player.channel.id:
                await ctx.reply('Necesitas estar en el mismo canal que el bot para poder usar este comando.', ephemeral=True)
                return

        try:
            track: wavelink.Search = await wavelink.Playable.search(flags.query, source=flags.source)
        except wavelink.LavalinkLoadException:
            await ctx.reply(f'No se pudo encontrar una canción llamada: {flags.query}', ephemeral=True)
            return

        resolved_track: wavelink.Playable

        if isinstance(track, list):
            if not track:
                await ctx.reply(f'No se pudo encontrar una canción llamada: {flags.query}', ephemeral=True)
                return

            resolved_track = track[0]
        elif isinstance(track, wavelink.Playlist):
            if not track.tracks:
                await ctx.reply(f'No se pudo encontrar una canción llamada: {flags.query}', ephemeral=True)
                return

            resolved_track = track.tracks[0]
        else:
            await ctx.reply(f'No se pudo encontrar ninguna canción llamada: {flags.query}', ephemeral=True)
            return

        embed = discord.Embed(color=self.bot.default_color)
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)

        if player.playing:
            embed.description = f"\N{INBOX TRAY} Se ha añadido a la cola la canción: {discord.utils.escape_markdown(f'{resolved_track.title} (de {resolved_track.author} en {resolved_track.album.name or resolved_track.title})')}"
            player.queue.put(resolved_track)
        else:
            embed.description = f"\N{MUSICAL NOTE} Ahora reproduciendo: {discord.utils.escape_markdown(f'{resolved_track.title} (de {resolved_track.author} en {resolved_track.album.name or resolved_track.title})')}"

        await ctx.send(content="", embed=embed)
        await player.play(resolved_track, replace=False)

    @music.command(name="pause")
    async def music_pause(self, ctx: GuildContext) -> None:
        """Alterna el pausado de una canción."""
        await ctx.defer()

        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.reply('¡Tienes que estar conectado a un canal de voz para poder utilizar este comando!', ephemeral=True)
            return

        player: wavelink.Player | None = ctx.voice_client  # type: ignore

        if player is None:
            await ctx.reply('No hay un reproductor activo, ¡conéctalo primero para poder pausar o reanudar una canción!', ephemeral=True)
            return

        if player.channel.id != ctx.author.voice.channel.id:
            await ctx.reply('¡Tienes que estar conectado en el mismo canal de voz que el reproductor para poder utilizar este comando!', ephemeral=True)
            return

        embed = discord.Embed(color=self.bot.default_color)
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)

        if player.paused:
            embed.description = "\N{BLACK RIGHT-POINTING TRIANGLE} Se ha reanudado el reproductor"
        else:
            embed.description = "\N{DOUBLE VERTICAL BAR} Se ha pausado el reproductor"

        await player.pause(not player.paused)
        await ctx.reply(content="", embed=embed)
        if ctx.channel.id != player.channel.id:
            await player.channel.send(embed=embed)

    @music.command(name="volume")
    @discord.app_commands.describe(
        volume="El nuevo volumen. Por defecto es 100."
    )
    async def music_volume(self, ctx: GuildContext, *, volume: commands.Range[int, 0, 100]) -> None:
        """Cambia el volumen de una canción, el valor por defecto es de 100"""
        await ctx.defer()

        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.reply('¡Tienes que estar conectado a un canal de voz para poder utilizar este comando!', ephemeral=True)
            return

        player: wavelink.Player | None = ctx.voice_client  # type: ignore

        if player is None:
            await ctx.reply('No hay un reproductor activo, ¡conéctalo primero para poder cambiar el volumen de una canción!', ephemeral=True)
            return

        if player.channel.id != ctx.author.voice.channel.id:
            await ctx.reply('¡Tienes que estar conectado en el mismo canal de voz que el reproductor para poder utilizar este comando!', ephemeral=True)
            return

        if 0 > volume or volume > 100:
            await ctx.reply('¡El volumen debe de estar entre 0 y 100!', ephemeral=True)
            return

        embed = discord.Embed(color=self.bot.default_color)
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        emoji = "\N{SPEAKER WITH ONE SOUND WAVE}" if volume < 50 else "\N{SPEAKER WITH THREE SOUND WAVES}"
        embed.description = f"{emoji} Se ha establecido el volumen a {volume}%"

        await ctx.reply(content="", embed=embed)
        await player.set_volume(volume)

        if ctx.channel.id != player.channel.id:
            await player.channel.send(embed=embed)

    @music.command(name="stop")
    async def music_stop(self, ctx: GuildContext) -> None:
        """Deja de reproducir la canción actual y desconecta el reproductor."""
        await ctx.defer()

        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.reply(
                "¡Tienes que estar conectado a un canal de voz para poder utilizar este comando!",
                ephemeral=True,
            )
            return

        player: wavelink.Player | None = ctx.voice_client  # type: ignore

        if player is None:
            await ctx.reply(
                "No hay un reproductor activo, ¡conéctalo primero para poder desconectar el reproductor!",
                ephemeral=True,
            )
            return

        if player.channel.id != ctx.author.voice.channel.id:
            await ctx.reply(
                "¡Tienes que estar conectado en el mismo canal de voz que el reproductor para poder utilizar este comando!",
                ephemeral=True,
            )
            return

        if player.playing:
            if player.queue:
                player.queue.clear()
            await player.stop(force=True)
        if player.paused is True:
            await player.pause(False)
        await player.disconnect()

        embed = discord.Embed(color=self.bot.default_color)
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.description = "\N{WHITE HEAVY CHECK MARK} Se ha desconectado el reproductor."

        await ctx.reply(content="", embed=embed)

        if ctx.channel.id != player.channel.id:
            await player.channel.send(embed=embed)

    @music.group(name="queue", fallback="view")
    async def music_queue(self, ctx: GuildContext) -> None:
        """Comprueba la cola y opciones de ella."""

        await ctx.defer()

        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.reply(
                "¡Tienes que estar conectado a un canal de voz para poder utilizar este comando!",
                ephemeral=True,
            )
            return

        player: wavelink.Player | None = ctx.voice_client  # type: ignore

        if player is None:
            await ctx.reply(
                "No hay un reproductor activo, ¡conéctalo primero para poder comprobar y manejar la cola de reproducción!",
                ephemeral=True,
            )
            return

        if player.channel.id != ctx.author.voice.channel.id:
            await ctx.reply(
                "¡Tienes que estar conectado en el mismo canal de voz que el reproductor para poder utilizar este comando!",
                ephemeral=True,
            )
            return

        embed = discord.Embed(color=self.bot.default_color)
        description: list[str] = []

        for track in player.queue:
            description.append(
                discord.utils.escape_markdown(f'{track.title} de {track.author}')
            )

        embed.description = ", ".join(description)

        if len(embed.description) > 4096:
            while (len(embed.description) > 4096):
                description.pop()
                embed.description = ", ".join(description)

        if not embed.description:
            embed.description = "La cola está vacía"

        if not player.auto_queue.is_empty:
            embed.set_footer(text="Este reproductor contiene canciones recomendadas de manera dinámica")

        await ctx.reply(content="", embed=embed)

    @music_queue.command(name="manage")
    async def music_queue_manage(self, ctx: GuildContext) -> None:
        """Gestiona la cola (cambiar modos, etc.)."""
        await ctx.defer()

        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.reply(
                "¡Tienes que estar conectado a un canal de voz para poder utilizar este comando!",
                ephemeral=True,
            )
            return

        player: wavelink.Player | None = ctx.voice_client  # type: ignore

        if player is None:
            await ctx.reply(
                "No hay un reproductor activo, ¡conéctalo primero para poder manejar la cola de reproducción!",
                ephemeral=True,
            )
            return

        if player.channel.id != ctx.author.voice.channel.id:
            await ctx.reply(
                "¡Tienes que estar conectado en el mismo canal de voz que el reproductor para poder utilizar este comando!",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"Gestión de la cola de reproducción de {ctx.guild.name}",
            color=self.bot.default_color,
        )
        embed.description = (
            "Los siguientes botones te permiten gestionar la cola de reproducción:\n"
            "- \N{CLOCKWISE RIGHTWARDS AND LEFTWARDS OPEN CIRCLE ARROWS}: Repite la cola de reproducción\n"
            "- \N{CLOCKWISE RIGHTWARDS AND LEFTWARDS OPEN CIRCLE ARROWS WITH CIRCLED ONE OVERLAY}: Repite la canción actual\n"
            "- \N{TWISTED RIGHTWARDS ARROWS}: Aleatoriza la cola de reproducción y la reproduce en bucle\n"
            "- \N{CLOCKWISE DOWNWARDS AND UPWARDS OPEN CIRCLE ARROWS}: Aleatoriza la cola de reproducción y añade canciones sugeridas\n"
            "- \N{PERMANENT PAPER SIGN}: Reproduce toda la cola, y añade canciones sugeridas\n"
            "- \N{BLACK RIGHT-POINTING TRIANGLE WITH DOUBLE VERTICAL BAR}: Reproduce la canción actual y pausa el reproductor\n"
            "- 'Mezclar': Aleatoriza la cola de reproducción actual, no disponible en ciertos modos."
        )
        view = ManageQueueView(ctx.author, player, embed)
        view.message = await ctx.reply(content="", embed=embed, view=view)

    async def cog_check(self, ctx: GuildContext) -> bool:  # type: ignore
        if not self.bot.wavelink_is_ready():
            await ctx.reply(
                'La función de música no está disponible en estos momentos, disculpe las molestias',
                ephemeral=True,
            )
            return False
        return True

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload) -> None:
        self.bot.logger.info(
            f'Node connected to {payload.node.uri} | Resumed: {payload.resumed} | Session ID: {payload.session_id}'
        )

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload) -> None:
        player = payload.player

        if player is None:
            return

        embed = discord.Embed(color=self.bot.default_color)
        embed.description = f"\N{MUSICAL NOTE} Ahora reproduciendo: {discord.utils.escape_markdown(f'{payload.track.title} (de {payload.track.author} en {payload.track.album.name or payload.track.title})')}"

        if payload.original:
            embed.set_footer(
                text=f'Reproduciendo a partir de: {payload.original.title} (de {payload.original.author} en {payload.original.album.name or payload.original.title})'
            )

        await player.channel.send(embed=embed)

        try:
            await player.channel.edit(
                status=f"\N{MUSICAL NOTE} {payload.track.title} - {payload.track.author}"  # type: ignore
            )
        except:  # NOQA: E722
            # if we cant set the status, then just ignore :v
            pass

    @commands.Cog.listener()
    async def on_wavelink_inactive_player(self, player: wavelink.Player) -> None:
        await player.disconnect()
        await player.channel.send('He estado 1 minuto sin reproducir ninguna canción, ¡y me he tenido que desconectar!')

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload) -> None:
        if payload.reason == 'loadFailed':
            if payload.player:
                embed = discord.Embed(color=self.bot.default_color)
                embed.description = f'\N{CROSS MARK} No se pudo cargar la canción {discord.utils.escape_markdown(f"{payload.track.title} (de {payload.track.author} en {payload.track.album.name or payload.track.title})")}'
                await payload.player.channel.send(embed=embed)
        else:
            return

    @commands.Cog.listener()
    async def on_wavelink_track_exception(self, payload: wavelink.TrackExceptionEventPayload) -> None:
        embed = discord.Embed(color=self.bot.default_color)
        track = discord.utils.escape_markdown(
            f"{payload.track.title} (de {payload.track.author} en {payload.track.album.name or payload.track.title})",
        )
        if payload.exception["severity"] == "common":
            embed.description = f":x: Un error ocurrió al intentar reproducir {track}"
        elif payload.exception["severity"] == "suspicious":
            embed.description = f":x: Un error (posiblemente por causas del servicio proporcionado al usar ``music play``) ocurrió al intentar reproducir {track}\nCausa: {payload.exception['cause']}"
        elif payload.exception["severity"] == "fault":
            embed.description = f":x: Un error desconocido e inesperado ocurrió al intentar reproducir {track}, inténtelo de nuevo más tarde.\nCausa: {payload.exception['cause']}"
        else:
            embed.description = f":x: El servidor tuvo un error inesperado y que no se pudo gestionar: {payload.exception['cause']}"
        await payload.player.channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_wavelink_track_stuck(self, payload: wavelink.TrackStuckEventPayload) -> None:
        embed = discord.Embed(color=self.bot.default_color)
        track = discord.utils.escape_markdown(
            f"{payload.track.title} (de {payload.track.author} en {payload.track.album.name or payload.track.title})"
        )
        embed.description = f":x: Se intentó reproducir {track} pero no se pudo tras {(payload.threshold * 1000):.2f} segundos"
        await payload.player.channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        if member.id == self.bot.user.id:  # pyright: ignore[reportOptionalMemberAccess]
            return

        voice_client: wavelink.Player | None = member.guild.voice_client  # type: ignore
        self.bot.logger.debug(
            f'Music on_voice_state_update debug log. Voice Client None?: {voice_client is None}'
        )
        if not voice_client:
            return

        if not before.channel and not after.channel:
            self.bot.logger.debug(
                'Voice state update did not have any channels, ignoring.'
            )
            return
        elif before.channel and not after.channel:
            # was connected, but disconnected
            self.bot.logger.debug(
                'Voice state update had a channel, but user disconnected from it, executing logic',
            )
            pass
        elif not before.channel and after.channel:
            # was not connected, and now it is
            self.bot.logger.debug(
                'Voice state update did not have a channel, but user is now connected to one, ignoring',
            )
            return
        elif before.channel and after.channel:
            if before.channel.id == after.channel.id:
                # did not change any channel, so we can return here
                self.bot.logger.debug(
                    'Voice state update did not update the channel user was connected to',
                )
                return
        else:
            # it would be strange we get here, let's assume we can execute the remaining logic
            self.bot.logger.debug(
                'Not handled state update, executing remaning logic'
            )

        channel = before.channel or after.channel

        if channel is None:
            self.bot.logger.debug(
                'Voice state user\'s connected channel is strangely none, so returning'
            )
            return

        if len(channel.members) == 1 and channel.members[0].id == self.bot.user.id:  # pyright: ignore[reportOptionalMemberAccess]
            if voice_client.playing:
                if voice_client.queue:
                    voice_client.queue.clear()
                await voice_client.stop(force=True)
            voice_client.auto_queue.clear()
            if voice_client.paused:
                await voice_client.pause(False)
            await voice_client.disconnect()
            await voice_client.channel.send('¡Me he desconectado del canal de voz ya que todos los miembros se fueron!')
