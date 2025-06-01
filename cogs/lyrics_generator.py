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
import datetime
import io
import os
from typing import TYPE_CHECKING, Any, Literal

try:
    import orjson as json
except ImportError:
    import json

import aiohttp
import discord
from discord.ext import commands, tasks
from playwright.async_api import async_playwright

if TYPE_CHECKING:
    from bot import LegacyBot, LegacyBotContext as Context

MISSING = discord.utils.MISSING


class SpotifyHandler:
    def __init__(self, bot: LegacyBot) -> None:
        self.client_id: str = os.environ['SPOTIFY_CLIENT_ID']
        self.client_secret: str = os.environ['SPOTIFY_CLIENT_SECRET']
        self.access_token: str = MISSING
        self.token_type: str = 'Bearer'
        self.expires_at: datetime.datetime | None = None
        self.bot: LegacyBot = bot

    async def create_token(self) -> None:
        async with self.bot.session.post(
            'https://accounts.spotify.com/api/token',
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            data={
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
            }
        ) as response:
            data = await response.json(loads=json.loads)

            if any(key not in data for key in ('access_token', 'token_type', 'expires_in')):
                raise RuntimeError('could not fetch the spotify access token')

            self.access_token = data['access_token']
            self.token_type = data['token_type']
            self.expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=int(data['expires_in']))

    async def search_songs(self, query: str, /) -> list[Song]:
        async with self.bot.session.get(
            'https://api.spotify.com/v1/search',
            params={
                'q': query,
                'type': 'track',
                'limit': 6,
            },
            headers={
                'Authorization': f'{self.token_type} {self.access_token}',
            }
        ) as response:
            data = await response.json(loads=json.loads)

            if 'tracks' not in data:
                raise RuntimeError(f'Could not fetch the tracks for query {query!r}')

            tracks = data['tracks']

            if 'items' not in tracks:
                raise RuntimeError('Spotify returned a malformed response')

            return Song._from_items(tracks['items'], self.bot.session)

    async def fetch_song_lyrics(self, artist: str, song: str) -> list[str]:
        async with self.bot.session.get(
            'https://lrclib.net/api/get',
            params={
                'track_name': song,
                'artist_name': artist,
            },
        ) as response:
            data = await response.json(loads=json.loads)

            if 'message' in data:
                raise RuntimeError(data['message'])

            return data['plainLyrics'].split('\n')


class Album:
    def __init__(self, data: dict[str, Any], session: aiohttp.ClientSession) -> None:
        self.name: str = data['name']
        self.album_type: str = data['album_type']
        self.artists: list[Artist] = Artist._from_artists(data['artists'])
        self.external_urls: dict[str, str] = data['external_urls']
        self.href: str = data['href']
        self.id: str = data['id']
        self.images: list[SpotifyAsset] = SpotifyAsset._from_images(data['images'], self.name, session)
        self.playable: bool = data['is_playable']
        self.release_date: str = data['release_date']
        self.track_count: int = data['total_tracks']
        self.type: Literal['album'] = data['type']
        self.uri: str = data['uri']

    @property
    def best_image(self) -> SpotifyAsset:
        l = sorted(self.images, key=lambda i: (i.height, i.width))
        return l[0]


class SpotifyAsset:
    def __init__(self, data: dict[str, Any], parent_name: str, session: aiohttp.ClientSession) -> None:
        self.height: int = data['height']
        self.width: int = data['width']
        self.url: str = data['url']
        self._parent_name: str = parent_name
        self._session: aiohttp.ClientSession = session

    async def save(self, fp: str | bytes | os.PathLike[Any] | io.BufferedIOBase, *, seek_begin: bool = True) -> int:
        data = await self.read()
        if isinstance(fp, io.BufferedIOBase):
            written = fp.write(data)
            if seek_begin:
                fp.seek(0)
            return written
        else:
            with open(fp, 'wb') as f:
                return f.write(data)

    async def read(self) -> bytes:
        async with self._session.get(self.url) as resp:
            return await resp.read()

    async def to_file(self) -> discord.File:
        return discord.File(await self.read(), filename=self.filename)

    @property
    def filename(self) -> str:
        return f'{self._parent_name}-{self.height}x{self.width}.jpeg'

    @classmethod
    def _from_images(cls, images: list[dict[str, Any]], parent_name: str, session: aiohttp.ClientSession) -> list[SpotifyAsset]:
        return [cls(d, parent_name, session) for d in images]


class Artist:
    def __init__(self, data: dict[str, Any]) -> None:
        self.external_urls: dict[str, str] = data['external_urls']
        self.href: str = data['href']
        self.id: str = data['id']
        self.name: str = data['name']
        self.type: Literal['artist'] = data['type']
        self.uri: str = data['uri']

    @classmethod
    def _from_artists(cls, data: list[dict[str, Any]]) -> list[Artist]:
        return [cls(d) for d in data]


class Song:
    def __init__(self, data: dict[str, Any], session: aiohttp.ClientSession) -> None:
        self.album: Album = Album(data['album'], session)
        self.artists: list[Artist] = Artist._from_artists(data['artists'])
        self.disc_number: int = int(data['disc_number'])
        self.duration: int = int(data['duration_ms'])
        self.explicit: bool = data['explicit']
        self.external_urls: dict[str, str] = data['external_urls']
        self.href: str = data['href']
        self.id: str = data['id']
        self.local: bool = data['is_local']
        self.playable: bool = data['is_playable']
        self.name: str = data['name']
        self.popularity: int = data['popularity']
        self.preview_url: str | None = data['preview_url']
        self.track: int = data['track_number']
        self.type: Literal['track'] = data['type']
        self.uri: str = data['uri']

    @property
    def thumbnail(self) -> SpotifyAsset:
        return self.album.best_image

    @property
    def thumbnail_url(self) -> str:
        return self.thumbnail.url

    @property
    def main_artist(self) -> Artist:
        return self.artists[0]

    @classmethod
    def _from_items(cls, items: list[dict[str, Any]], session: aiohttp.ClientSession) -> list[Song]:
        return [cls(d, session) for d in items]


class SelectSongView(discord.ui.LayoutView):
    container = discord.ui.Container()

    def __init__(self, options: list[Song], author_id: int) -> None:
        super().__init__(timeout=180.0)
        self.author_id: int = author_id
        self.songs: list[Song] = options
        self.message: discord.Message = MISSING
        self.add_items_to_container()

    async def interaction_check(self, interaction: discord.Interaction[LegacyBot]) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                'You can not use this selects!',
                ephemeral=True,
            )
            return False
        return True

    def add_items_to_container(self) -> None:
        self.container.clear_items()

        self.container.accent_colour = discord.Colour.blurple()
        select_options: list[discord.SelectOption] = []

        for song in self.songs:
            section = discord.ui.Section(
                f'**Name:** {song.name} | **Artist(s):** {", ".join(a.name for a in song.artists)}',
                f'**Album:** {song.album.name} | **Track:** {song.track}',
                f'**Explicit:** {"Yes" if song.explicit else "No"} | **Popularity:** {song.popularity}/100',
                accessory=discord.ui.Thumbnail(song.thumbnail_url)
            )
            select_options.append(
                discord.SelectOption(
                    label=f'{song.main_artist.name} - {song.name}',
                    value=song.id,
                )
            )
            self.container.add_item(section)

        self.container.add_item(
            discord.ui.ActionRow(
                ChooseSongSelect(options=select_options, songs=self.songs),
            ),
        )


    async def on_timeout(self) -> None:
        if self.message is not MISSING:
            for child in self.walk_children():
                if hasattr(child, 'disabled'):
                    child.disabled = True
            await self.message.edit(view=self)


class ChooseSongSelect(discord.ui.Select['SelectSongView']):
    def __init__(self, options: list[discord.SelectOption], songs: list[Song]) -> None:
        super().__init__(
            placeholder='Choose the song to get the lyrics of...',
            options=options,
            disabled=False,
        )
        self.songs: dict[str, Song] = {song.id: song for song in songs}

    async def callback(self, interaction: discord.Interaction['LegacyBot']) -> None:
        song_id = self.values[0]
        song = self.songs.get(song_id)

        if song is None:
            await interaction.response.send_message(
                'The song you selected was not found, try again later.',
                ephemeral=True,
            )
            return

        cog: LyricsGenerator | None = interaction.client.get_cog('LyricsGenerator')  # type: ignore
        if not cog:
            await interaction.response.send_message(
                'This feature is not currently available, try again later.',
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        try:
            lyrics = await cog.handler.fetch_song_lyrics(song.main_artist.name, song.name)
        except RuntimeError as error:
            await interaction.followup.send(
                str(error),
                ephemeral=True,
            )
        view = LyricsGeneratorView(lyrics, interaction.client, interaction.user.id, song)
        await interaction.edit_original_response(
            view=view,
        )


class AddLyricsButton(discord.ui.Button['LyricsGeneratorView']):
    def __init__(self, sect_id: int, page: int) -> None:
        super().__init__(
            label='Select Line',
            style=discord.ButtonStyle.grey,
        )

        self.sect_id: int = sect_id
        self.page: int = page

    async def callback(self, interaction: discord.Interaction[LegacyBot]) -> None:
        assert self.view

        if self.sect_id in self.view.selected_lyrics:
            center = len(self.view.lyrics) / 2
            if self.sect_id < center:
                to_remove = [i for i in self.view.selected_lyrics if i <= self.sect_id]
            else:
                to_remove = [i for i in self.view.selected_lyrics if i >= self.sect_id]

            for i in to_remove:
                self.view.selected_lyrics.pop(i, None)

            self.view.disable_items()
            await interaction.response.edit_message(view=self.view)
            return

        if self.view.selected_lyrics:
            selected_lines = sorted(self.view.selected_lyrics.keys())
            max_prev_line = min(selected_lines) - 1
            max_next_line = max(selected_lines) + 1

            if self.sect_id not in (max_prev_line, max_next_line):
                await interaction.response.send_message(
                    'You can not add this line!',
                    ephemeral=True,
                )
                return

        section = self.view.get_item(self.sect_id)
        if section is None or not isinstance(section, discord.ui.Section):
            await interaction.response.send_message(
                'Invalid section ID, try again later.',
                ephemeral=True,
            )
            return

        lyrics = section.children[0]
        if not isinstance(lyrics, discord.ui.TextDisplay):
            await interaction.response.send_message(
                'Invalid section value, try again later.',
                ephemeral=True,
            )
            return

        self.view.selected_lyrics[self.sect_id] = lyrics.content
        self.view.disable_items()
        await interaction.response.edit_message(view=self.view)


class LyricsGeneratorView(discord.ui.LayoutView):
    container = discord.ui.Container()
    action_row = discord.ui.ActionRow()

    def __init__(self, lyrics: list[str], bot: LegacyBot, author_id: int, song: Song) -> None:
        super().__init__(timeout=3600)

        self.song: Song = song
        self.lyrics: list[str] = lyrics
        self.paged_lyrics: dict[int, list[str]] = {
            page_id: page
            for page_id, page
            in enumerate(
                discord.utils.as_chunks([l for l in self.lyrics if l], max_size=10)
            ) if page
        }
        self.current_page: int = 0
        self.selected_lyrics: dict[int, str] = {}
        self.author_id: int = author_id
        self.add_items_to_container()
        self.load_paginator()

    def disable_items(self) -> None:
        if not self.selected_lyrics:
            for child in self.container.children:
                if isinstance(child, discord.ui.Section) and isinstance(child.accessory, AddLyricsButton):
                    child.accessory.disabled = False
                    child.accessory.label = "Select Line"
            return

        selected_lyrics = self.selected_lyrics.keys()

        selected_ids = list(selected_lyrics)
        prev_line = min(selected_ids) - 1
        next_line = max(selected_ids) + 1

        adjacent_ids = {prev_line, next_line}

        for child in self.container.children:
            if not isinstance(child, discord.ui.Section):
                continue
            button = child.accessory
            if not isinstance(button, AddLyricsButton):
                continue

            section_id = child.id
            if section_id in self.selected_lyrics:
                button.disabled = False
                button.label = "Deselect Line"
            elif section_id in adjacent_ids:
                button.disabled = False
                button.label = "Select Line"
            else:
                button.disabled = True
                button.label = "Select Line"

    def add_items_to_container(self) -> None:
        self.container.clear_items()

        sect_id = sum(len(self.paged_lyrics[i]) for i in range(self.current_page)) + 1

        for lyric in self.paged_lyrics.get(self.current_page, []):
            if not lyric:
                continue
            self.container.add_item(
                discord.ui.Section(
                    discord.ui.TextDisplay(lyric),
                    accessory=AddLyricsButton(sect_id, self.current_page),
                    id=sect_id,
                ),
            )
            sect_id += 1

    def load_paginator(self) -> None:
        self.action_row.clear_items()

        self.action_row.add_item(
            MovePage(
                lambda c: c - 1,
                'Prev',
                disabled=self.current_page == 0,
            ),
        )
        self.action_row.add_item(
            discord.ui.Button(
                label=f'Page {self.current_page + 1}/{len(self.paged_lyrics)}',
                disabled=True,
                style=discord.ButtonStyle.grey,
            ),
        )
        self.action_row.add_item(
            MovePage(
                lambda c: c + 1,
                'Next',
                disabled=self.current_page + 1 >= len(self.paged_lyrics),
            ),
        )
        self.action_row.add_item(
            GenerateLyrics(
                view=self,
                disabled=False,
            )
        )

    async def interaction_check(self, interaction: discord.Interaction['LegacyBot']) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                'You can not use any of this items!',
                ephemeral=True,
            )
            return False
        return True


class GenerateLyrics(discord.ui.Button['LyricsGeneratorView']):
    def __init__(self, disabled: bool, view: LyricsGeneratorView) -> None:
        super().__init__(
            style=discord.ButtonStyle.green,
            label='Generate Lyrics',
            disabled=disabled,
        )
        self.parent: LyricsGeneratorView = view

    async def callback(self, interaction: discord.Interaction[LegacyBot]) -> None:
        if not self.parent.selected_lyrics:
            await interaction.response.send_message(
                'You need to select at least 1 line of lyrics to generate an image of them!',
                ephemeral=True,
            )
            return

        await interaction.response.edit_message(
            view=discord.ui.LayoutView().add_item(
                discord.ui.TextDisplay('Generating lyrics, please wait...'),
            ).add_item(
                discord.ui.TextDisplay('This message will be automatically updated when the process is done!'),
            )
        )
        view = LyricsImageSettingsView(self.parent)
        buffer = await view.generate_image()
        await interaction.edit_original_response(view=view, attachments=[discord.File(buffer, 'image.png')])


DEFAULT_CSS = """
@import url("https://fonts.googleapis.com/css2?family=Poppins:ital,wght@0,100;0,200;0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,100;1,200;1,300;1,400;1,500;1,600;1,700;1,800;1,900&display=swap");

* {
    box-sizing: border-box;
    font-family: "Poppins", sans-serif;

    --background-color: rgba(246, 246, 246, 1);
    --background-text-color: rgba(18, 55, 64, 1);
    --surface-light-color: rgba(84, 154, 171, 0.1);
    --surface-color: rgba(84, 154, 171, 0.3);
    --surface-text-color: rgba(18, 55, 64, 0.85);
    --primary-color: rgba(241, 128, 45, 1);
    --primary-text-color: rgba(246, 246, 246, 1);
    --error-color: rgba(240, 40, 30, 0.3);
    --error-text-color: rgba(240, 40, 30, 1);

    --cubic-ease-out: cubic-bezier(0.215, 0.61, 0.355, 1);
}

.dark-mode, .dark-mode * {
    --background-color: rgba(20, 20, 20, 1);
    --background-text-color: rgba(72, 220, 255, 0.8);
    --surface-light-color: rgba(84, 154, 171, 0.1);
    --surface-color: rgba(84, 154, 171, 0.25);
    --surface-text-color: rgba(72, 220, 255, 0.7);
    --primary-color: rgba(241, 128, 45, 0.95);
    --primary-text-color: rgba(246, 246, 246, 1);
    --error-color: rgba(240, 40, 30, 0.2);
    --error-text-color: rgba(240, 40, 30, 1);
}

[contenteditable] {
    outline: none;
}

.cloneable {
    display: none!important;
}

body {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    padding: 0;
    margin: 0;
    background: var(--background-color);
    color: var(--background-text-color);
}

h1, h2 {
    margin: 0;
    padding: 1.5rem 0 1.1rem;
    font-size: 1.6rem;
}

.surface {
    background: var(--surface-color);
    color: var(--surface-text-color);
}

.primary {
    background: var(--primary-color);
    color: var(--primary-text-color);
}

a {
    text-decoration: none;
    font-weight: 600;
    color: inherit
}

a:hover {
    text-decoration: underline;
}

main {
    flex: 1;
    display: flex;
    justify-content: center;
    align-items: flex-start;
}

header {
    position: relative;
}

header > .go-to-screen, #download, #last-go-back {
    position: absolute;
    top: calc(50% + 0.2rem);
    left: -1rem;
    transform: translate(-100%, -50%);
    border: 0;
    border-radius: 0.5rem;
    padding: 0.5rem;
    background-color: var(--surface-light-color);
    color: var(--surface-text-color);
    transition: 150ms var(--cubic-ease-out);
}

header > .go-to-screen.right, #download {
    right: -1rem;
    left: auto;
    transform: translate(100%, -50%);
}

header > .go-to-screen:hover, #download:hover, #last-go-back:hover {
    cursor: pointer;
    background-color: var(--surface-color);
}

footer {
    text-align: center;
    padding: 2.1rem;
    height: 8rem;
    font-size: 1.2rem;
}

#dark-mode-toggle {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 0.3rem;
    font-weight: 600;
    padding-top: 0.5rem;
}

#dark-mode-toggle:hover {
    cursor: pointer;
}

#dark-mode-toggle::before {
    content: "Switch to dark";
}

.dark-mode #dark-mode-toggle::before {
    content: "Switch to light";
}

#dark-mode-toggle > span::after {
    content: "dark_mode";
}

.dark-mode #dark-mode-toggle > span::after {
    content: "light_mode";
}

.song-image {
    display: flex;
    flex-direction: column;
    padding: 1.2rem 1rem 1rem;
    max-width: 20rem;
    width: 95%;
    background-color: rgba(84, 154, 171, 1);
    color: rgba(0, 0, 0, 0.95);
    border-radius: 1.5rem;
    transition: 200ms var(--cubic-ease-out);
}

.light-text .song-image {
    color: rgba(255, 255, 255, 0.95);
}

.song-image > .header {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding-bottom: 1.5rem;
}

.song-image > .header > img {
    height: 2.4rem;
    aspect-ratio: 1;
    border-radius: 0.5rem;
    object-fit: cover;
}

.song-image > .header .name {
    font-size: 0.95rem;
    font-weight: 700;
    line-height: 1.2rem;
    padding-bottom: 0.1rem;
}

.song-image > .header .authors {
    font-size: 0.75rem;
    line-height: 1rem;
    font-weight: 600;
    color: rgba(0, 0, 0, 0.6);
    transition: 200ms var(--cubic-ease-out);
}

.light-text .song-image > .header .authors {
    color: rgba(255, 255, 255, 0.7);
}

.song-image > .lyrics {
    font-size: 1.2rem;
    font-weight: 700;
    line-height: 1.5rem;
    padding-bottom: 0.2rem;
}

.song-image > .spotify {
    filter: brightness(0) saturate(100%) invert(0%) sepia(5%) saturate(22%) hue-rotate(164deg) brightness(96%) contrast(105%);
    height: 0;
    padding: 0;
    overflow: hidden;
    transition: 200ms var(--cubic-ease-out);
}

.spotify-tag .song-image > .spotify {
    height: 3rem;
    padding: 1.2rem 0 0.3rem;
}

.song-image > .spotify > img {
    height: 100%;
}

.light-text .song-image > .spotify {
    filter: brightness(0) saturate(100%) invert(100%) sepia(0%) saturate(0%) hue-rotate(93deg) brightness(103%) contrast(103%);
}

@keyframes search-indicator {
    0% {
        width: 20%;
        left: 0%;
        transform: translate(-200%, 0);
    }

    33% {
        width: 50%;
        left: 20%;
        transform: translate(0%, 0);
    }

    66% {
        width: 40%;
        left: 60%;
        transform: translate(0%, 0);
    }

    100% {
        width: 10%;
        left: 100%;
        transform: translate(100%, 0);
    }
}

.searching {
    padding: 2rem 0 1rem;
    position: relative;
    overflow: hidden;
    transition: 200ms var(--cubic-ease-out);
}

.searching::after {
    content: "";
    position: absolute;
    bottom: 0;
    background-color: var(--background-text-color);
    height: 0.3rem;
    opacity: 1;
    transition: 100ms;
    animation: search-indicator 1s linear infinite;
}

.searching.hidden {
    padding: 0;
    font-size: 0;
}

.searching.hidden::after {
    opacity: 0;
    height: 0;
}

.error {
    background-color: var(--error-color);
    color: var(--error-text-color);
    padding: 1rem;
    border-radius: 0.5rem;
    margin-top: 2rem;
    text-align: center;
    font-size: 0.9rem;
    transition: 250ms var(--cubic-ease-out);
}

.error.hidden {
    margin-top: 0;
    padding: 0;
    font-size: 0;
    transition: 150ms var(--cubic-ease-out);
}

/**
 * Screens
 */
.lyrics-image-screen {
    width: 100%;
    overflow: hidden;
    opacity: 1;
    transition: width 500ms ease-in-out, opacity 300ms ease-in-out 200ms;
}

.lyrics-image-screen.hidden {
    opacity: 0;
    width: 0%;
    transition: width 500ms ease-in-out, opacity 300ms;
}

.screen-wrapper {
    width: 100vw;
    min-height: calc(100vh - 8rem);
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    transition: transform 500ms ease-in-out;
}

.hidden.left .screen-wrapper {
    transform: translate(-100%, 0);
}

/* Screen 1: Search form */
.search-form header {
    text-align: center;
}

.search-form form {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    gap: 1rem;
    width: 100%;
}

.search-form form > input {
    padding: 1rem;
    border: none;
    border-radius: 0.5rem;
    outline: none;
    width: 80%;
    max-width: 25rem;
}

.search-form form > button {
    text-align: center;
    padding: 1rem 1.5rem;
    border: none;
    border-radius: 0.5rem;
    outline: none;
    font-weight: 600;
    opacity: 1;
    transition: 200ms var(--cubic-ease-out);
}

.search-form form > button:hover {
    cursor: pointer;
    padding: 1rem 3rem;
}

.search-form form > button:disabled {
    font-size: 0;
    padding: 0;
    opacity: 0;
}

/* Screen 2: Song selection */
.search-results .song-selection {
    display: flex;
    justify-content: space-between;
    row-gap: 2rem;
    max-width: 50rem;
    padding: 2rem;
    flex-wrap: wrap;
}

.select-song {
    width: 30%;
    padding: 1rem;
    background-color: var(--surface-light-color);
    border-radius: 0.5rem;
    transition: scale 200ms var(--cubic-ease-out),
        background-color 200ms var(--cubic-ease-out);
}

.select-song:hover {
    cursor: pointer;
    background-color: var(--surface-color);
    scale: 1.05;
}

.select-song img {
    width: 100%;
    aspect-ratio: 1;
    object-fit: cover;
    object-position: center 0;
    opacity: 1;
    border-radius: 0.5rem;
    transition: scale 150ms var(--cubic-ease-out),
        aspect-ratio 400ms var(--cubic-ease-out),
        opacity 600ms var(--cubic-ease-out);
}

.select-song:hover img {
    scale: 1.05;
}

.hidden .select-song img {
    aspect-ratio: 10;
    opacity: 0;
    transition: aspect-ratio 400ms var(--cubic-ease-out) 100ms,
        opacity 400ms var(--cubic-ease-out) 100ms;
}

.select-song .name {
    font-weight: 700;
    padding-top: 0.5rem;
    transition: 300ms var(--cubic-ease-out);
}

.hidden .select-song .name {
    font-size: 0;
    padding-top: 0;
    transition: 300ms var(--cubic-ease-out) 100ms;
}

.select-song .authors {
    font-weight: 600;
    font-size: 0.8rem;
    transition: 300ms var(--cubic-ease-out);
}

.hidden .select-song .authors {
    font-size: 0;
    transition: 300ms var(--cubic-ease-out) 100ms;
}

/* Screen 3: Lines selection */
.lines-selection {
    padding-top: 1.5rem;
    width: 80%;
    max-width: 30rem;
}

.select-line {
    padding: 1rem;
    margin-bottom: 1rem;
    border-radius: 0.5rem;
    background-color: var(--surface-light-color);
    text-align: center;
    font-size: 1.1rem;
    font-weight: 600;
    width: 100%;
    margin: 0 auto 1rem;
    transition: padding 400ms var(--cubic-ease-out),
        margin-bottom 400ms var(--cubic-ease-out),
        font-size 400ms var(--cubic-ease-out),
        width 400ms var(--cubic-ease-out),
        background-color 200ms var(--cubic-ease-out),
        scale 200ms var(--cubic-ease-out);
}

.select-line:hover {
    cursor: pointer;
    background-color: var(--surface-color);
    scale: 1.05;
}

.hidden .select-line,
.select-line.hidden {
    padding: 0;
    margin-bottom: 0;
    font-size: 0;
    width: 0;
}

.select-line.selected {
    background-color: var(--primary-color);
    color: var(--primary-text-color);
}

/* Screen 4: Final options and download */
.final-options header {
    margin-bottom: 1rem;
}

.final-options .searching {
    margin-bottom: 2rem;
}

.final-options .searching.hidden {
    margin-bottom: 0;
}

.color-selection {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    row-gap: 0.8rem;
    max-width: 15rem;
    width: 80%;
    padding: 2rem 1rem;
    transition: 200ms var(--cubic-ease-out);
}

.hidden .color-selection {
    padding: 0 1rem;
}

.color-selection > div {
    width: 21%;
    aspect-ratio: 1;
    border-radius: 50%;
    color: transparent;
    transition: 150ms var(--cubic-ease-out);
}

.color-selection > div:hover {
    cursor: pointer;
    scale: 1.1;
}

.hidden .color-selection > div {
    width: 0;
}

#custom-color {
    display: flex;
    justify-content: center;
    align-items: center;
    color: var(--background-text-color);
    border: 1px solid var(--background-text-color);
}

#custom-color > input {
    height: 0;
    width: 0;
    padding: 0;
    border: none;
}

#custom-color > label:hover {
    cursor: pointer;
}

.switch-container {
    display: flex;
    align-items: center;
    max-width: 15rem;
    width: 80%;
    padding: 0rem 1rem 1rem;
    transition: 200ms var(--cubic-ease-out);
}

.switch-container:hover {
    cursor: pointer;
}

.hidden .switch-container {
    font-size: 0;
    padding: 0;
}

.switch {
    position: relative;
    width: 4rem;
    height: 2rem;
    border-radius: 1rem;
    border: 1px solid var(--background-text-color);
    margin-right: 1rem;
    transition: 200ms var(--cubic-ease-out);
}

.hidden .switch {
    height: 0;
}

.switch::after {
    content: "";
    display: block;
    position: absolute;
    top: 50%;
    left: 0.25rem;
    transform: translate(0, -50%);
    height: 1.5rem;
    aspect-ratio: 1;
    background-color: var(--background-text-color);
    border-radius: 50%;
    transition: 200ms var(--cubic-ease-out);
}

.light-text #light-text .switch::after {
    left: calc(100% - 1.75rem);
}

.spotify-tag #spotify-tag .switch::after {
    left: calc(100% - 1.75rem);
}

.additional-bg #additional-bg .switch::after {
    left: calc(100% - 1.75rem);
}

@media screen and (max-width: 450px) {
    .select-song {
        width: 45%;
    }
}
"""

DEFAULT_HTML = """
<!DOCTYPE html>
<head>
  <style>
  {css}
  </style>
</head>
<body>
  <div class="{light_mode}">
    <div class="song-image" style="background-color: rgb( {br}, {bg}, {bb} )">
        <div class="header">
        <img src="{thumbnail}" alt="album-cover">
        <div>
            <div class="name">{songname}</div>
            <div class"authors">{songauthors}</div>
        </div>
        </div>
        <div class="lyrics">
          {lines}
        </div>
      {spotify}
    </div>
  </div>
</body>
"""

SPOTIFY_DIV = """
<div>
  <img src="https://upload.wikimedia.org/wikipedia/commons/2/26/Spotify_logo_with_text.svg">
</div>
"""


class LyricsImageSettingsView(discord.ui.LayoutView):
    container = discord.ui.Container()

    def __init__(self, parent: LyricsGeneratorView) -> None:
        self.selected_lyrics = parent.selected_lyrics
        self.parent = parent
        self.raw_colour: str = '#008fd1'
        self.colour: discord.Colour = discord.Colour.from_str(self.raw_colour)
        self.light_text: bool = False
        self.spotify_logo: bool = False
        self.browser = None
        super().__init__(timeout=3600)

    def get_replace_dict(self) -> dict[str, Any]:
        return {
            "light_mode": "" if self.light_text is False else "light-text",
            "br": self.colour.r,
            "bg": self.colour.g,
            "bb": self.colour.b,
            "thumbnail": self.parent.song.thumbnail_url,
            "songname": self.parent.song.name,
            "songauthors": ", ".join(a.name for a in self.parent.song.artists),
            "lines": '\n<br>'.join(self.selected_lyrics.values()).removesuffix('<br>'),
            "spotify": SPOTIFY_DIV if self.spotify_logo else "",
            "css": DEFAULT_CSS,
        }

    async def on_timeout(self) -> None:
        if self.browser:
            await self.browser.close(reason='Session finalised')

    def get_html(self) -> str:
        return DEFAULT_HTML.format_map(self.get_replace_dict())

    async def generate_image(self) -> io.BytesIO:
        html = self.get_html()
        async with async_playwright() as p:
            if self.browser is None:
                self.browser = browser = await p.chromium.launch()
            else:
                browser = self.browser
            page = await browser.new_page()
            await page.set_content(html, wait_until='load')
            await page.wait_for_selector('.song-image')
            elem = page.locator('.song-image')
            ss = await elem.screenshot(type='png', omit_background=True)
            await page.close(reason='Screenshot taken')
            ret = io.BytesIO(ss)

        self.update_view()
        return ret

    def update_view(self) -> None:
        self.container.clear_items()

        self.container.accent_colour = self.colour
        self.container.add_item(
            discord.ui.MediaGallery(
                discord.MediaGalleryItem(
                    'attachment://image.png',
                ),
            ),
        )
        self.container.add_item(
            discord.ui.ActionRow(ChangeColourSelect(self.raw_colour)),
        )
        self.container.add_item(
            discord.ui.ActionRow(
                #ToggleConfigButton(self.spotify_logo, 'spotify_logo', label='Toggle Spotify Logo'),
                ToggleConfigButton(self.light_text, 'light_text', label='Toggle Light Text'),
                ReturnToLyricsSelector(self.parent),
            ),
        )


class ReturnToLyricsSelector(discord.ui.Button['LyricsImageSettingsView']):
    def __init__(self, parent: LyricsGeneratorView) -> None:
        self.parent: LyricsGeneratorView = parent
        super().__init__(
            style=discord.ButtonStyle.grey,
            label='Go Back',
        )

    async def callback(self, interaction: discord.Interaction[LegacyBot]) -> None:
        await interaction.response.edit_message(attachments=[], view=self.parent)


class ToggleConfigButton(discord.ui.Button['LyricsImageSettingsView']):
    def __init__(self, val: bool, attr: str, label: str) -> None:
        super().__init__(
            style=discord.ButtonStyle.blurple,
            label=label,
        )
        self.attr: str = attr
        self.val: bool = val

    async def callback(self, interaction: discord.Interaction[LegacyBot]) -> None:
        await interaction.response.defer()

        assert self.view

        self.val = not self.val
        setattr(self.view, self.attr, self.val)
        file = await self.view.generate_image()
        await interaction.edit_original_response(
            view=self.view,
            attachments=[discord.File(file, 'image.png')],
        )


class ChangeColourSelect(discord.ui.Select['LyricsImageSettingsView']):
    def __init__(self, default: str) -> None:
        options = []

        for label, value in (
            ('Lochmara', '#008fd1'),
            ('Hippie Blue', '#549aab'),
            ('Pistachio', '#8fc00c'),
            ('Highland', '#729962'),
            ('Limed Oak', '#a2904e'),
            ('Indochine', '#cd6800'),
            ('Red Orange', '#fc302f'),
        ):
            options.append(
                discord.SelectOption(
                    label=label,
                    value=value,
                    default=value == default,
                )
            )

        super().__init__(
            options=options,
            placeholder='Choose the background colour...',
        )

    async def callback(self, interaction: discord.Interaction[LegacyBot]) -> None:
        await interaction.response.defer()

        assert self.view

        self.view.raw_colour = self.values[0]
        self.view.colour = discord.Colour.from_str(self.view.raw_colour)

        file = discord.File(
            await self.view.generate_image(),
            'image.png',
        )
        await interaction.edit_original_response(view=self.view, attachments=[file])


class MovePage(discord.ui.Button['LyricsGeneratorView']):
    def __init__(self, key: Callable[[int], int], label: str, disabled: bool = False) -> None:
        self.key: Callable[[int], int] = key
        super().__init__(
            style=discord.ButtonStyle.blurple,
            label=label,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction[LegacyBot]) -> None:
        assert self.view
        assert self.label is not None

        self.view.current_page = self.key(self.view.current_page)
        self.view.add_items_to_container()
        self.view.load_paginator()
        self.view.disable_items()

        await interaction.response.edit_message(view=self.view)


class LyricsGenerator(commands.Cog):
    """Generate lyric images for your favourite song!"""

    display_emoji = '\N{MUSICAL NOTE}'

    def __init__(self, bot: LegacyBot) -> None:
        self.bot: LegacyBot = bot
        self.handler: SpotifyHandler = SpotifyHandler(bot)

    async def cog_load(self) -> None:
        await self.handler.create_token()
        self.refresh_token.start()

    async def cog_unload(self) -> None:
        self.refresh_token.stop()

    @tasks.loop(hours=1)
    async def refresh_token(self) -> None:
        if self.handler.expires_at is None:
            await self.handler.create_token()
            return

        await discord.utils.sleep_until(self.handler.expires_at)
        await self.handler.create_token()

    @commands.hybrid_command(name='generate-lyrics')
    @commands.cooldown(
        1, 30, commands.BucketType.user,
    )
    async def generate_lyrics(self, ctx: Context, *, query: str) -> None:
        """Generates a song's lyrics.

        Parameters
        ----------
        query
            The song to find and create the lyrics of.
        """
        try:
            songs = await self.handler.search_songs(query)
        except RuntimeError as error:
            await ctx.reply(str(error))
            return

        view = SelectSongView(songs, ctx.author.id)
        await ctx.reply(view=view)


async def setup(bot: LegacyBot) -> None:
    await bot.add_cog(LyricsGenerator(bot))
