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

from collections.abc import Callable, ItemsView, Iterator, KeysView, ValuesView
import datetime
import io
import os
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeVar

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

    from _typeshed import SupportsRichComparison

    K = TypeVar('K', bound=SupportsRichComparison)
else:
    K = TypeVar('K')


MISSING = discord.utils.MISSING
V = TypeVar('V')


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
            },
        ) as response:
            data = await response.json(loads=json.loads)

            if any(key not in data for key in ('access_token', 'token_type', 'expires_in')):
                raise RuntimeError('could not fetch the spotify access token')

            self.access_token = data['access_token']
            self.token_type = data['token_type']
            self.expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
                seconds=int(data['expires_in'])
            )

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
            },
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


class OrderedDict(Generic[K, V]):
    def __init__(self) -> None:
        self._data: dict[K, V] = {}

    def __setitem__(self, key: K, value: V) -> None:
        self._data[key] = value
        self._data = dict(sorted(self._data.items(), key=lambda i: i[0]))

    def __bool__(self) -> bool:
        return bool(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __getitem__(self, key: K) -> V:
        return self._data[key]

    def __contains__(self, key: Any) -> bool:
        return key in self._data

    def __iter__(self) -> Iterator[K]:
        return iter(self._data)

    def keys(self) -> KeysView[K]:
        return self._data.keys()

    def values(self) -> ValuesView[V]:
        return self._data.values()

    def items(self) -> ItemsView[K, V]:
        return self._data.items()

    def pop(self, key: K, default: Any = None) -> Any:
        return self._data.pop(key, default)


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
    def _from_images(
        cls, images: list[dict[str, Any]], parent_name: str, session: aiohttp.ClientSession
    ) -> list[SpotifyAsset]:
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
                accessory=discord.ui.Thumbnail(song.thumbnail_url),
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
                    child.disabled = True  # pyright: ignore[reportAttributeAccessIssue]
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
            for page_id, page in enumerate(discord.utils.as_chunks([l for l in self.lyrics if l], max_size=10))
            if page
        }
        self.current_page: int = 0
        self.selected_lyrics: OrderedDict[int, str] = OrderedDict()
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
            view=discord.ui.LayoutView()
            .add_item(
                discord.ui.TextDisplay('Generating lyrics, please wait...'),
            )
            .add_item(
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

body {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    padding: 0;
    margin: 0;
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

.spotify-tag #spotify-tag .switch::after {
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
        self.playwright = None
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
        if self.playwright:
            await self.playwright.stop()

    def get_html(self) -> str:
        return DEFAULT_HTML.format_map(self.get_replace_dict())

    async def generate_image(self) -> io.BytesIO:
        html = self.get_html()

        if self.playwright is None:
            self.playwright = p = await async_playwright().start()
        else:
            p = self.playwright

        if self.browser is None:
            self.browser = browser = await p.chromium.launch()
        else:
            browser = self.browser

        page = await browser.new_page()
        await page.set_content(html, wait_until='load')
        await page.wait_for_selector('.song-image')
        elem = page.locator('.song-image')
        ss = await elem.screenshot(omit_background=True, scale='css')
        await page.close(reason='Screenshot finalised')

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
                # ToggleConfigButton(self.spotify_logo, 'spotify_logo', label='Toggle Spotify Logo'),
                ToggleConfigButton(self.light_text, 'light_text', label='Toggle Light Text'),
                FinishButton(self),
                ReturnToLyricsSelector(self, self.parent),
            ),
        )


class FinishButton(discord.ui.Button['LyricsImageSettingsView']):
    def __init__(self, parent: LyricsImageSettingsView) -> None:
        self.parent = parent
        super().__init__(
            style=discord.ButtonStyle.green,
            label='Finish',
        )

    async def callback(self, interaction: discord.Interaction[LegacyBot]) -> None:
        ret = await self.parent.generate_image()
        file = discord.File(ret, filename='image.png')
        view = discord.ui.LayoutView().add_item(
            discord.ui.MediaGallery(discord.MediaGalleryItem('attachment://image.png')),
        )
        await self.parent.on_timeout()
        self.parent.stop()
        await interaction.response.edit_message(attachments=[file], view=view)


class ReturnToLyricsSelector(discord.ui.Button['LyricsImageSettingsView']):
    def __init__(self, prev: LyricsImageSettingsView, parent: LyricsGeneratorView) -> None:
        self.parent: LyricsGeneratorView = parent
        self.prev = prev
        super().__init__(
            style=discord.ButtonStyle.grey,
            label='Go Back',
        )

    async def callback(self, interaction: discord.Interaction[LegacyBot]) -> None:
        await self.prev.on_timeout()
        self.prev.stop()
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
        1,
        30,
        commands.BucketType.user,
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
