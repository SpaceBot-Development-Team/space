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

from typing import TYPE_CHECKING, Any, Callable, Literal, TypeVar, overload

import asyncpg
import discord

if TYPE_CHECKING:
    from bot import LegacyBot

ValueFactory = Callable[[str, Any, Literal['save', 'load', 'delete']], Any]
ReplaceableFactory = Callable[[str, Any, int], str]
D = TypeVar('D')
MISSING = discord.utils.MISSING

def default_value_factory(name: str, value: Any, mode: Literal['save', 'load', 'delete']) -> Any:
    return value

def default_replaceable_factory(name: str, value: Any, pos: int) -> str:
    return f'${pos}'


class DBStore:
    """Represents a dict like object that saves the data on a DB table.

    The keys represent the primary keys (either composite or single) and the
    value map represents a {db_field: db_value} map.

    Parameters
    ----------
    bot: :class:`LegacyBot`
        The bot attached to this store.
    table: :class:`str`
        The table to where obtain and store the data.
    keys: Union[List[:class:`str`], :class:`str`]
        The primary keys of the table. If multiple keys are provided the map keys
        will be tuples of ``(primary, key, values): {...}``. If it is a single item or just a string,
        it will be just the value received by the db: ``primary_key_value: {...}``.
    value_factory: Callable[[:class:`str`, Any, :class:`str`], Any]
        The callable to use to convert the values. This takes 3 parameters: ``name``, ``value``, and ``mode``.
        ``name`` is the field name and ``value`` the value that was either obtained or to be converter,
        which is determined by ``mode``.
    query_replaceable_factory: Callable[[:class:`str`, Any, :class:`int`], :class:`str`]
        The callable to use to convert the replaceables. This takes 3 parameters: ``name``, ``value`` and ``pos``.
        ``name`` is the field name, ``value`` the value that is going to be converted, and ``pos`` the $ string position
        for help purposes.

        This should return a string with ``$<pos>``. This is useful if you want to convert, for example, dicts to jsonb objects:
        ``$<pos>::jsonb``.
    """

    __slots__ = (
        'bot',
        'table',
        '_keys',
        '_data',
        '_factory',
        '_replaceable_factory',
    )

    def __init__(
        self,
        bot: LegacyBot,
        table: str,
        keys: list[str] | str,
        *,
        value_factory: ValueFactory = default_value_factory,
        query_replaceable_factory: ReplaceableFactory = default_replaceable_factory,    
    ) -> None:
        self.bot: LegacyBot = bot
        self.table: str = table
        self._factory: ValueFactory = value_factory or default_value_factory
        self._replaceable_factory: ReplaceableFactory = query_replaceable_factory
        self._keys: list[str] = keys if isinstance(keys, list) else [keys]
        self._data: dict[Any, dict[str, Any]] = {}

    def _primary_keys(self) -> str:
        return ', '.join(f'"{key}"' for key in self._keys)

    def _get_replaceables(self, start: int, fields: dict[str, Any]) -> list[str]:
        return [self._replaceable_factory(field, value, pos) for pos, (field, value) in enumerate(fields, start)]

    def _get_where_query(self, fields: dict[str, Any], start: int = 1) -> str:
        checks = []

        for no, (field, value) in enumerate(fields.items(), start):
            checks.append(
                f'{field} = {self._replaceable_factory(field, value, no)}'
            )

        return ' AND '.join(checks)

    def _get_update_query(self, fields: dict[str, Any], *, start: int = 1) -> str:
        return f'UPDATE "{self.table}" ({", ".join(fields)}) SET ({", ".join(self._get_replaceables(start, fields))})'

    def _get_insert_query(self, fields: dict[str, Any], *, start: int = 1) -> str:
        return f'INSERT INTO "{self.table}" ({", ".join(fields.keys())}) VALUES ({", ".join(self._get_replaceables(start, fields))})'

    def _run_factories(self, values: dict[str, Any], mode: Literal['save', 'load', 'delete']) -> list[Any]:
        ret = []

        for name, value in values.items():
            ret.append(
                self._factory(name, value, mode)
            )
        return ret

    async def _remove_key(self, values: dict[str, Any]) -> None:
        pk_check = self._get_where_query(
            values,
        )

        async with self.bot.get_connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    f'DELETE FROM "{self.table}" WHERE {pk_check}',
                    *self._run_factories(values, 'delete'),
                )

    async def load(self) -> None:
        """Loads all the items from the table."""

        rows: list[asyncpg.Record] = await self.bot.pool.fetch(f'SELECT * FROM "{self.table}"')

        for row in rows:
            if len(self._keys) == 1:
                pk = row[self._keys[0]]
            else:
                pk = tuple([row[k] for k in self._keys])

            data = {}
            for k, v in row.items():
                if k in self._keys:
                    continue
                data[k] = v
            self._data[pk] = data

    def clear_cache(self) -> None:
        """Clears all the internal cache.

        .. note::

            This **does not** remove from the database.

        .. warning::

            By doing this, :meth:`.get` will stop working and will always
            return ``None``. To fix this you will need to call :meth:`.load`
            for the cache to be populated.
        """
        self._data.clear()

    @overload
    def get(self, key: tuple[Any, ...]) -> dict[str, Any] | None:
        ...

    @overload
    def get(self, key: tuple[Any, ...], default: D) -> dict[str, Any] | D:
        ...

    @overload
    def get(self, key: Any) -> dict[str, Any] | None:
        ...

    @overload
    def get(self, key: Any, default: D) -> dict[str, Any] | D:
        ...

    def get(self, key: Any, default: D = None) -> dict[str, Any] | D:
        """Gets a key from the store.

        Parameters
        ----------
        key: Union[Any, Tuple[Any, ...]]
            The key to get, this should be a tuple if the primary keys was a sequence
            of more than 1 items.
        default: Any
            The default value to return in case no value was found in the store. Defaults
            to ``None``.

        Returns
        -------
        Dict[:class:`str`, Any]
            The data of the key, or the default.
        """
        return self._data.get(key, default)

    @overload
    async def pop(self, key: tuple[Any, ...]) -> dict[str, Any]:
        ...

    @overload
    async def pop(self, key: Any) -> Any:
        ...

    async def pop(self, key: Any) -> dict[str, Any]:
        """Pops a key from the store.

        Parameters
        ----------
        key: Union[Any, Tuple[Any, ...]]
            The key to pop, this should be a tuple if the primary keys was a sequence
            of more than 1 items.

        Raises
        ------
        KeyError
            The key was not found in the store.

        Returns
        -------
        Dict[:class:`str`, Any]
            The data of the key, or the default.
        """

        data = self._data.pop(key)

        # if we are here, this means no KeyError was raised so lets just
        # remove it from the db

        values_v = list(key) if isinstance(key, tuple) else [key]
        values = dict(zip(self._keys, values_v))
        await self._remove_key(values)
        return data

    @overload
    async def set(self, key: tuple[Any, ...], value: dict[str, Any]) -> None:
        ...

    @overload
    async def set(self, key: Any, value: dict[str, Any]) -> None:
        ...

    async def set(self, key: Any, value: dict[str, Any]) -> None:
        """Updates a key's value.

        Parameters
        ----------
        key: Any
            The key to update.
        value: Dict[:class:`str`, Any]
            The value to set.
        """

        exists = key in self._data
        self._data[key] = value
        value_keys = list(value.keys())
        value_values = list(value.values())

        resolved_keys = list(key) if isinstance(key, tuple) else [key]
        resolved_value_map = dict(zip(self._keys + value_keys, resolved_keys + value_values))
        resolved_key_map = dict(zip(self._keys, resolved_keys))

        if exists:
            base = self._get_update_query(value)
            where = self._get_where_query(resolved_key_map, len(value) + 1)
            values = self._run_factories(value, 'save')
            query = f'{base} WHERE {where}'
        else:
            query = self._get_insert_query(resolved_value_map)
            values = self._run_factories(resolved_value_map, 'save')

        async with self.bot.get_connection() as conn:
            async with conn.transaction():
                await conn.execute(query, *values)

    @overload
    async def update(self, mapping: dict[tuple[Any, ...], dict[str, Any]]) -> None:
        ...

    @overload
    async def update(self, mapping: dict[Any, dict[str, Any]]) -> None:
        ...

    async def update(self, mapping: dict[Any, dict[str, Any]]) -> None:
        """Bulk updates the store with a mapping.

        .. note::

            This is the same as bulk calling :meth:`.set` with ``key``
            being the map key and ``value`` the value.

        Parameters
        ----------
        mapping: Dict[Any, Dict[:class:`str`, Any]]
            The map to update with.
        """

        for key, value in mapping.items():
            try:
                value.update(self._data[key])
            except KeyError:
                pass
            await self.set(key, value)

    @overload
    async def delete(self, key: tuple[Any, ...]) -> None:
        ...

    @overload
    async def delete(self, key: Any) -> None:
        ...

    async def delete(self, key: Any) -> None:
        """Delets a key from the store.

        Unlike :meth:`.pop` this will try to delete from the database even if it
        is not present.

        Parameters
        ----------
        key:
            The key to remove.
        """

        values_v = list(key) if isinstance(key, tuple) else [key]
        values = dict(zip(self._keys, values_v))
        await self._remove_key(values)
        self._data.pop(key, None)
