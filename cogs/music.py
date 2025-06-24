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

from collections.abc import Callable
import logging
import os
import asyncio
from typing import TYPE_CHECKING, Generic, Literal, TypeVar, overload

import wavelink

import discord
from discord.ext import commands

try:
    from async_timeout import timeout as atimeout
except ImportError:
    from asyncio import timeout as atimeout

if TYPE_CHECKING:
    from bot import LegacyBot, LegacyBotContext as Context

_log = logging.getLogger(__name__)
K = TypeVar('K')


class SelectSongView(discord.ui.LayoutView):
    container = discord.ui.Container()

    def __init__(self, songs: list[wavelink.Playable]) -> None:
        self.songs: list[wavelink.Playable] = songs[:10]
        self.chosen_song: wavelink.Playable | None = None
        super().__init__(timeout=60)
        self.add_items_to_container()

    def add_items_to_container(self) -> None:
        self.container.clear_items()
        options: list[discord.SelectOption] = []

        for index, song in enumerate(self.songs):
            description = (
                f'**Track name:** {song.title}\n' f'**Track author:** {song.author}\n' f'**Album:** {song.album.name}'
            )

            if song.uri:
                description += f'\n**Track URL:** [Click Here](<{song.uri}>)'
            if song.recommended:
                description += '\n-# This song was recommended by the autoplayer'

            accessory = discord.ui.Button(
                label='No artwork',
                disabled=True,
            )
            if song.artwork:
                accessory = discord.ui.Thumbnail(song.artwork)

            self.container.add_item(
                discord.ui.Section(
                    description,
                    accessory=accessory,
                    id=index,
                ),
            )
            options.append(
                discord.SelectOption(
                    label=f'{song.author} - {song.title}',
                    value=str(index),
                ),
            )

        self.container.add_item(discord.ui.ActionRow(ChooseSongSelect(options)))

    async def on_timeout(self) -> None:
        self.stop()

    async def wait_for_song(self) -> wavelink.Playable | None:
        await self.wait()
        return self.chosen_song


class ChooseSongSelect(discord.ui.Select['SelectSongView']):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(placeholder='Choose the song to play...', options=options)

    async def callback(self, interaction: discord.Interaction[LegacyBot]) -> None:
        if not self.view:
            await interaction.response.send_message(
                'This is currently unavailable, try again later.',
                ephemeral=True,
            )
            return

        song_index = self.values[0]

        try:
            song = self.view.songs[int(song_index)]
        except IndexError:
            await interaction.response.send_message(
                'The song you provided is not currently available, try again later.',
                ephemeral=True,
            )
            return

        self.view.chosen_song = song
        self.view.stop()
        section = self.view.get_item(int(song_index))
        if not section:
            await interaction.response.defer()
            return
        await interaction.response.edit_message(
            view=discord.ui.LayoutView()
            .add_item(
                discord.ui.TextDisplay('Chosen song:'),
            )
            .add_item(section)
        )


class LockDict(Generic[K]):
    def __init__(self, initial: dict[K, asyncio.Lock] | None = None) -> None:
        self.__data: dict[K, asyncio.Lock] = initial or {}

    def __getitem__(self, key: K) -> asyncio.Lock:
        try:
            lock = self.__data[key]
        except KeyError:
            lock = self.__data[key] = asyncio.Lock()
        return lock

    def __setitem__(self, key: K, value: asyncio.Lock) -> None:
        self.__data[key] = value

    def get(self, key: K) -> asyncio.Lock:
        return self[key]

    @overload
    def set(self, key: K) -> None:
        ...

    @overload
    def set(self, key: K, value: asyncio.Lock) -> None:
        ...

    def set(self, key: K, value: asyncio.Lock | None = None) -> None:
        value = value or asyncio.Lock()
        self[key] = value


class Music(commands.Cog):
    """Commands that allow the bot to play music on your server."""

    def __init__(self, bot: LegacyBot) -> None:
        self.bot: LegacyBot = bot
        self.disconnect_task: dict[int, asyncio.Task[None]] = {}
        self.locks: LockDict[int] = LockDict()

    async def cog_load(self) -> None:
        if self.bot.wavelink_node_pool.nodes:
            # prevent from "clone connecting" nodes
            return

        for server in range(1, 7):
            host = os.getenv(f'LAVALINK_{server}_HOST')
            password = os.getenv(f'LAVALINK_{server}_PASS')

            if not host or not password:
                _log.warning(f'Lavalink server number {server} is not correctly set')
                continue

            try:
                _log.info(f'Attempting first connection to server number {server} at {host}')
                async with atimeout(30.0):
                    await self.bot.wavelink_node_pool.connect(
                        nodes=[
                            wavelink.Node(
                                password=password,
                                client=self.bot,
                                uri=f'https://{host}:443',
                                retries=2,
                            ),
                        ],
                    )
            except (asyncio.TimeoutError, asyncio.CancelledError):
                _log.warning(f'Timed out connecting to server number {server} at {host}')
                continue
            else:
                _log.info(f'Successfully connected to server number {server} at {host}')
                return

        _log.info('Music is not available, unloading cog.')
        await self.bot.remove_cog(self.__cog_name__)

    @commands.hybrid_group(name='music')
    async def music(self, ctx: Context) -> None:
        """The commands for the music handling"""

    @music.command(name='join')
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def vc_join(self, ctx: Context) -> None:
        """Joins your vc"""
        if ctx.voice_client:
            await ctx.reply(':x: | There is already an active music player on this server!')
            return

        async with ctx.typing():
            if not ctx.author.voice or not ctx.author.voice.channel:
                await ctx.reply(':x: | You are not in a voice channel!')
                return
            await ctx.author.voice.channel.connect(cls=wavelink.Player)
        await ctx.reply(':white_check_mark: | Successfully joined the voice channel!')

    @music.command(name='play')
    @commands.cooldown(1, 15, commands.BucketType.member)
    async def vc_play(self, ctx: Context, source: wavelink.TrackSource | None = None, *, query: str) -> None:
        """Searchs for a song to play on the provided source. If there is a song currently playing, it is added
        to the queue.

        Parameters
        ----------
        source:
            Where to search the song from.
        query:
            The song to search.
        """

        if source is None:
            source = wavelink.TrackSource.YouTubeMusic

        player = ctx.voice_client

        if not player or not isinstance(player, wavelink.Player):
            await ctx.reply(':x: | There is no current voice player!')
            return

        if not ctx.author.voice or not ctx.author.voice.channel or ctx.author.voice.channel.id != player.channel.id:
            await ctx.reply(':x: | You must be on the same channel as the bot in order to manage the music!')
            return

        async with ctx.typing():
            songs = await wavelink.Playable.search(query, source=source, node=player.node)

            if isinstance(songs, wavelink.Playlist):
                await ctx.reply(':x: | You need to provide a song, not a playlist!')
                return

            if not songs:
                await ctx.reply(':x: | No songs were found')
                return

            if len(songs) == 1:
                song = songs[0]
            else:
                view = SelectSongView(songs)
                await ctx.reply(view=view)
                song = await view.wait_for_song()

                if not song:
                    await ctx.reply(':x: | You did not choose the song to add')
                    return

            if not player.playing:
                await player.play(song)
            else:
                player.queue.put(song)

            player.autoplay = wavelink.AutoPlayMode.partial

        await ctx.reply(f':white_check_mark: | Added ``{song.title}`` by ``{song.author}`` to the queue')

    @music.command(name='toggle', aliases=['resume', 'pause'])
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def vc_toggle(self, ctx: Context, *, paused: bool | None = None) -> None:
        """Toggles the pause on the player.

        Parameters
        ----------
        paused:
            Manually toggle the paused context to this value.
        """

        player = ctx.voice_client

        if not player or not isinstance(player, wavelink.Player):
            await ctx.reply(':x: | There is no current voice player!')
            return

        if not ctx.author.voice or not ctx.author.voice.channel or ctx.author.voice.channel.id != player.channel.id:
            await ctx.reply(':x: | You must be on the same channel as the bot in order to manage the music!')
            return

        if paused is None:
            paused = not player.paused

        async with ctx.typing():
            await player.pause(paused)

        await ctx.reply(f':white_check_mark: | Successfully {"paused" if paused else "resumed"} the music')

    @music.command(name='skip')
    @commands.cooldown(1, 30, commands.BucketType.member)
    async def vc_skip(self, ctx: Context) -> None:
        """Skips to the next song of the queue. If there are no more songs, the player stops."""

        player = ctx.voice_client

        if not player or not isinstance(player, wavelink.Player):
            await ctx.reply(':x: | There is no current voice player!')
            return

        if not ctx.author.voice or not ctx.author.voice.channel or ctx.author.voice.channel.id != player.channel.id:
            await ctx.reply(':x: | You must be on the same channel as the bot in order to manage the music!')
            return

        if not player.playing:
            await ctx.reply(':x: | The player is not playing anything!')
            return

        async with ctx.typing():
            await player.skip(force=True)

        await ctx.reply(':white_check_mark: | Successfully skipped the current song!')

    @music.command(name='disconnect')
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def vc_disconnect(self, ctx: Context) -> None:
        """Disconnects the player from the voice."""

        player = ctx.voice_client

        if not player or not isinstance(player, wavelink.Player):
            await ctx.reply(':x: | There is no current voice player!')
            return

        if not ctx.author.voice or not ctx.author.voice.channel or ctx.author.voice.channel.id != player.channel.id:
            await ctx.reply(':x: | You must be on the same channel as the bot in order to manage the music!')
            return

        await player.disconnect(force=True)

    @music.group(name='volume', fallback='set')
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def vc_volume(self, ctx: Context, *, volume: commands.Range[int, 0, 100]) -> None:
        """Sets the player volume to the one provided.

        Parameters
        ----------
        volume:
            The volume to set. Must be between 0 and 100.
        """

        player = ctx.voice_client

        if not player or not isinstance(player, wavelink.Player):
            await ctx.reply(':x: | There is no current voice player!')
            return

        if not ctx.author.voice or not ctx.author.voice.channel or ctx.author.voice.channel.id != player.channel.id:
            await ctx.reply(':x: | You must be on the same channel as the bot in order to manage the music!')
            return

        async with ctx.typing():
            await player.set_volume(volume)

        await ctx.reply(f':white_check_mark: | Successfully set the volume to {volume}%')

    @vc_volume.command(name='reset')
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def vc_volume_reset(self, ctx: Context) -> None:
        """Resets the player volume to the original one."""

        player = ctx.voice_client

        if not player or not isinstance(player, wavelink.Player):
            await ctx.reply(':x: | There is no current voice player!')
            return

        if not ctx.author.voice or not ctx.author.voice.channel or ctx.author.voice.channel.id != player.channel.id:
            await ctx.reply(':x: | You must be on the same channel as the bot in order to manage the music!')
            return

        async with ctx.typing():
            await player.set_volume(100)

        await ctx.reply(':white_check_mark: | Successfully resetted the players volume')

    @music.command(name='autoplay', fallback='set')
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def vc_autoplay(self, ctx: Context, *, type: Literal['enabled', 'disabled'] | None = None) -> None:
        """Sets the autoplay for the voice player.

        Parameters
        ----------
        type:
            The type of autoplay to set
        """

        if not await ctx.is_premium():
            await ctx.buy_premium('In order to use this feature you need to buy [Space] Premium!')
            return

        player = ctx.voice_client

        if not player or not isinstance(player, wavelink.Player):
            await ctx.reply(':x: | There is no current voice player!')
            return

        if not ctx.author.voice or not ctx.author.voice.channel or ctx.author.voice.channel.id != player.channel.id:
            await ctx.reply(':x: | You must be on the same channel as the bot in order to manage the music!')
            return

        if type is None:
            if player.autoplay in (wavelink.AutoPlayMode.disabled, wavelink.AutoPlayMode.partial):
                type = 'enabled'
                type_enum = wavelink.AutoPlayMode.enabled
            else:
                type = 'disabled'
                type_enum = wavelink.AutoPlayMode.partial
        elif type == 'disabled':
            type_enum = wavelink.AutoPlayMode.partial
        elif type == 'enabled':
            type_enum = wavelink.AutoPlayMode.enabled
        else:
            await ctx.reply(f':x: | An invalid autoplay type was provided: {type!r}')
            return

        player.autoplay = type_enum
        await ctx.reply(f':white_check_mark: | Successfully set the player autplay mode to {type}')

    @music.command(name='queue')
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def vc_queue(self, ctx: Context) -> None:
        """Shows the first 10 tracks on the queue."""

        player = ctx.voice_client

        if not player or not isinstance(player, wavelink.Player):
            await ctx.reply(':x: | There is no current voice player!')
            return

        queue = (player.queue._items + player.auto_queue._items)[:10]
        if (not player.queue and not player.auto_queue) or not queue:
            await ctx.reply('There are no tracks on the queue!')
            return

        container = discord.ui.Container(accent_colour=discord.Colour.random(seed=queue[0].title))

        for track in queue:
            container.add_item(
                discord.ui.Section(
                    f'**Track name:** {track.title}\n**Track author:** {track.author}\n'
                    + (
                        f'**Album:** {track.album.name}'
                        + (f'\n**Track URL:** [Click Here](<{track.uri}>)' if track.uri else '')
                        + ('\n-# This song was recommended by the autplayer' if track.recommended else '')
                    ),
                    accessory=(
                        discord.ui.Thumbnail(track.artwork)
                        if track.artwork
                        else discord.ui.Button(label='No artwork', disabled=True)
                    ),
                ),
            )

        await ctx.reply(view=discord.ui.LayoutView().add_item(container))

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload) -> None:
        _log.debug(f'Node {payload.node!r} is now ready | Resumed: {payload.resumed} | Session ID: {payload.session_id}')

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload) -> None:
        if not payload.player:
            return

        song = payload.track
        embed = discord.Embed(
            title='Now Playing...',
            description=(
                f'**Track name:** {song.title}\n'
                f'**Track author:** {song.author}\n'
                f'**Album:** {song.album.name}\n'
                + (f'**Track URL:** [Click Here](<{song.uri}>)\n' if song.uri else '')
                + ('-# This song was recommended by the autoplayer' if song.recommended else '')
            ),
            colour=discord.Colour.random(seed=song.title),
        ).set_thumbnail(url=song.artwork)

        await payload.player.channel.send(embed=embed)

        # voice statuses may be broken because, discord is discord, nothing else
        # if this worked niced, if it didnt, meh
        try:
            await payload.player.channel.edit(status=f'Playing {song.title} by {song.author}'[:500])  # type: ignore
        except:
            pass

    @commands.Cog.listener('on_voice_state_update')
    async def bot_should_disconnect(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        player = member.guild.voice_client
        guild_id = member.guild.id

        if not player or not isinstance(player, wavelink.Player):
            # We don't care about non-playing things
            return

        player_id = player.channel.id

        lock = self.locks.get(guild_id)
        async with lock:
            if before.channel and not after.channel:
                # user disconnected a voice channel
                if before.channel.id != player_id:
                    return

                if not before.channel.members:
                        task = self.disconnect_task.get(guild_id)

                        if task:
                            # disconnect is already scheduled
                            return

                        task = self.disconnect_task[guild_id] = self.bot.loop.create_task(self.do_disconnect(player))
                        task.add_done_callback(self.remove_task(guild_id))
            elif not before.channel and after.channel:
                # user connected a voice channel
                if after.channel.id != player_id:
                    return

                task = self.disconnect_task.get(guild_id)

                if not task:
                    # bot was not scheduled for disconnect
                    return

                if not task.done():
                    task.cancel()

            elif before.channel and after.channel:
                # user could have changed channels
                if before.channel.id == after.channel.id:
                    # the user may have just updated their mute / deaf state or other, ignore
                    return

                if before.channel.id == player_id and after.channel.id != player_id:
                    # user left the player channel
                    task = self.disconnect_task.get(guild_id)

                    if task:
                        # disconnect is already scheduled
                        return

                    task = self.disconnect_task[guild_id] = self.bot.loop.create_task(self.do_disconnect(player))
                    task.add_done_callback(self.remove_task(guild_id))
                elif before.channel.id != player_id and after.channel.id == player_id:
                    # user joined the player channel
                    task = self.disconnect_task.get(guild_id)

                    if not task:
                        # bot was not scheduled for disconnect
                        return

                    if not task.done():
                        task.cancel()
                else:
                    # unhandled case, ignore
                    return
            else:
                # unhandled case, ignore
                return

    async def do_disconnect(self, player: wavelink.Player) -> None:
        # wait 1 minute before fully disconnecting
        await asyncio.sleep(60)

        if player.connected:
            if player.playing:
                await player.stop(force=True)
            await player.disconnect()

    def remove_task(self, guild_id: int) -> Callable[[asyncio.Task], None]:
        def inner(task: asyncio.Task) -> None:
            self.disconnect_task.pop(guild_id, None)
        return inner


async def setup(bot: LegacyBot) -> None:
    await bot.add_cog(Music(bot))
