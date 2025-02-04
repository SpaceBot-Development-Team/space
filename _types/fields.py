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

from collections.abc import Mapping
from typing import Any, Callable, Generic, Iterable, Literal, TypeVar, overload
import warnings

import tortoise

from .warns import WarnConfig, Warn

from tortoise import Model
from tortoise.fields import Field
from tortoise.fields.data import JsonDumpsFunc, JsonLoadsFunc, JSON_LOADS, JSON_DUMPS
from tortoise.exceptions import FieldError, IncompleteInstanceError, IntegrityError
from tortoise.backends.asyncpg.client import AsyncpgDBClient

T = TypeVar("T")
TM = TypeVar("TM", bound="CompositePrimaryKeyTable")
A = TypeVar("A")
L = TypeVar("L", bound="Literal[A]")  # pyright: ignore


class WarnsDataField(Field[dict], WarnConfig):
    """
    Warns Data Field

    This field can store dicts of any JSON-compliant structure.

    Parameters
    ----------
    encoder: Callable[[Any], Any]
        The custom JSON encoder.
    decoder: Callable[[Any], Any]
        The custom JSON decoder.
    """

    SQL_TYPE = "JSON"
    indexable = False

    class _db_postgres:
        SQL_TYPE = "JSONB"

    class _db_mssql:
        SQL_TYPE = "NVARCHAR(MAX)"

    class _db_oracle:
        SQL_TYPE = "NCLOB"

    def __init__(
        self,
        encoder: JsonDumpsFunc = JSON_DUMPS,
        decoder: JsonLoadsFunc = JSON_LOADS,
        default: WarnConfig | None = None,
        **kwargs: Any,
    ) -> None:
        if default is not None:
            kwargs["default"] = default.to_dict()
        super().__init__(**kwargs)

        self.encoder = encoder
        self.decoder = decoder

    def to_db_value(
        self, value: str | WarnConfig, instance: type[Model] | Model
    ) -> str | None:
        self.validate(value)

        if isinstance(value, (str, bytes)):
            try:
                value = self.decoder(value)
            except Exception as exc:
                raise FieldError(f"Value {value} is not a valid JSON value") from exc
            return self.encoder(value)

        if isinstance(value, dict):
            try:
                return self.encoder(value)
            except Exception as exc:
                raise FieldError(f"Value {value} is not a valid JSON value") from exc
        return None if value is None else self.encoder(value.to_dict())

    def to_python_value(self, value: str | bytes | dict) -> WarnConfig | None:
        if isinstance(value, (str, bytes)):
            try:
                return WarnConfig(data=self.decoder(value))
            except Exception as exc:
                raise FieldError(f"Value {value} is not a valid JSON value") from exc
        if isinstance(value, dict):
            value = WarnConfig(data=value)  # type: ignore

        self.validate(value)
        return value  # type: ignore


class Array(Generic[T], Field[list[T]], list[T]):
    """
    List field.

    Parameters
    ----------
    encoder: Callable[[Any], Any]
        The custom JSON encoder.
    decoder: Callable[[Any], Any]
        The custom JSON decoder.
    """

    SQL_TYPE = "JSON"
    indexable = False

    class _db_postgres:
        SQL_TYPE = "JSONB"

    class _db_mssql:
        SQL_TYPE = "NVARCHAR(MAX)"

    class _db_oracle:
        SQL_TYPE = "NCLOB"

    def __init__(
        self,
        encoder: JsonDumpsFunc = JSON_DUMPS,
        decoder: JsonLoadsFunc = JSON_LOADS,
        default: list[T] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(default=default, **kwargs)

        self.encoder = encoder
        self.decoder = decoder

    def to_db_value(
        self, value: str | list[T], instance: type[Model] | Model
    ) -> str | None:
        self.validate(value)

        if isinstance(value, (str, bytes)):
            try:
                self.decoder(value)
            except Exception as exc:
                raise FieldError(f"Value {value} is not a valid JSON value") from exc
            return value
        return None if value is None else self.encoder(value)

    def to_python_value(self, value: str | bytes | list[T]) -> list[T] | None:
        if isinstance(value, (str, bytes)):
            try:
                return self.decoder(value)
            except Exception as exc:
                raise FieldError(f"Value {value} is not a valid JSON value") from exc
        self.validate(value)
        return value  # type: ignore


class WarnsField(Field[dict[str, Warn]], dict[str, Warn]):
    """warn field"""

    SQL_TYPE = "JSON"
    indexable = False

    class _db_postgres:
        SQL_TYPE = "JSONB"

    class _db_mssql:
        SQL_TYPE = "NVARCHAR(MAX)"

    class _db_oracle:
        SQL_TYPE = "NCLOB"

    def __init__(
        self,
        encoder: JsonDumpsFunc = JSON_DUMPS,
        decoder: JsonLoadsFunc = JSON_LOADS,
        default: dict | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(default=default, **kwargs)

        self.encoder = encoder
        self.decoder = decoder

    def to_db_value(
        self,
        value: str | dict[str, Warn],
        instance: type[Model] | Model,
    ) -> str | None:
        self.validate(value)

        if isinstance(value, (str, bytes)):
            try:
                self.decoder(value)
            except Exception as exc:
                raise FieldError(f"Value {value} is invalid JSON value") from exc
            return value  # type: ignore
        return (
            None
            if value is None
            else self.encoder({k: v.to_dict() for k, v in value.items()})
        )

    def to_python_value(self, value: str | bytes | dict) -> dict[str, Warn] | None:
        if isinstance(value, (str, bytes)):
            try:
                v: dict[str, dict[str, Any]] = self.decoder(value)
            except Exception as exc:
                raise FieldError(
                    f"Value {value if isinstance(value, str) else value.decode()} is invalid JSON value"
                ) from exc
        else:
            v = value  # type: ignore
        self.validate(v)  # type: ignore

        new_dict: dict[str, Warn] = {}

        for key, data in v.items():
            obj = Warn.from_data(
                id=key,
                data=data,  # type: ignore
            )
            new_dict[key] = obj
        return new_dict


RESERVED_DB_NAMES = ("user",)


def composite_primary_keys(*keys: str) -> Callable[[type[TM]], type[TM]]:
    """Adds a composite primary key to a model."""

    def decorator(cls: type[TM]) -> type[TM]:
        resolved_fields: dict[str, Field | Any] = dict.fromkeys(keys)
        for name, field in cls._meta.fields_map.items():
            if name in resolved_fields:
                field.null = False
                resolved_fields[name] = field
        if "id" in cls._meta.fields_map:
            field = cls._meta.fields_map["id"]
            if field.pk:
                try:
                    cls._meta.fields.remove("id")
                except KeyError:
                    pass
                cls._meta.fields_db_projection.pop("id", None)
                cls._meta.fields_db_projection_reverse.pop("id", None)
                try:
                    cls._meta.db_fields.remove("id")
                except KeyError:
                    pass
                if hasattr(cls, "id"):
                    delattr(cls, "id")
                del cls._meta.fields_map["id"]  # Remove autocreated pk
        cls.__composite_primary_keys__ = list(keys)
        cls.__resolved_composite_primary_keys__ = resolved_fields
        return cls

    return decorator


class CompositePrimaryKeyTable(Model):
    """Represents a composite primary key table."""

    __composite_primary_keys__: list[str]
    __resolved_composite_primary_keys__: Mapping[str, Field]

    async def save(  # type: ignore
        self,
        using_db: AsyncpgDBClient | None = None,
        update_fields: Iterable[str] | None = None,
        force_create: bool = False,
        force_update: bool = False,
    ) -> None:
        await self._set_async_default_field()
        db = using_db or self._choose_db(True)
        executor = db.executor_class(model=self.__class__, db=db)
        if self._partial:
            if update_fields:
                for field in update_fields:
                    if not hasattr(self, self._meta.pk_attr):
                        raise IncompleteInstanceError(
                            f"{self.__class__.__name__} is a partial model without a primary key fetched. Partial update not available"
                        )
                    if not hasattr(self, field):
                        raise IncompleteInstanceError(
                            f"{self.__class__.__name__} is a partial model, field {field!r} is not available"
                        )
            else:
                raise IncompleteInstanceError(
                    f"{self.__class__.__name__} is a partial model, can only be saved with the relevant update_field provided"
                )
        await self._pre_save(db, update_fields)
        if force_create:
            await executor.execute_insert(self)
            created = True
        elif force_update:
            rows = await executor.execute_update(self, update_fields)
            if not rows:
                raise IntegrityError(
                    f"Cannnot update object that does not exist. PKs: {self.__composite_primary_keys__}"
                )
            created = False
        else:
            fields = self._meta.fields_map
            s_pos = 1
            s_pos_values: list[Any] = []
            string = (
                'INSERT INTO "%s" (%s) VALUES (%s) ON CONFLICT (%s) DO UPDATE SET %s;'
            )
            table_name = self._meta.db_table
            safe_field_names = list(
                field if field not in RESERVED_DB_NAMES else f'"{field}"'
                for field in fields
            )
            insert_fields_string = ", ".join(safe_field_names)
            safe_pks_names = list(
                (
                    field.model_field_name
                    if field.model_field_name not in RESERVED_DB_NAMES
                    else f'"{field.model_field_name}"'
                )
                for field in self.__resolved_composite_primary_keys__.values()
            )
            conflictive_pks = ", ".join(safe_pks_names)
            insert_values_strings: list[str] = []
            for field in safe_field_names:
                value = getattr(self, field.replace('"', ""))
                value_string = f"${s_pos}"
                insert_values_strings.append(value_string)
                s_pos += 1
                s_pos_values.append(
                    fields[field.replace('"', "")].to_db_value(value, self)
                )
            insert_values_string = ", ".join(insert_values_strings)
            update_values_strings: list[str] = []
            for field in safe_field_names:
                if field in safe_pks_names:
                    continue  # Ignore primary keys, they already exist if the DO UPDATE clause gets called

                value = getattr(self, field.replace('"', ""))
                value_string = f"{field}=${s_pos}"
                update_values_strings.append((value_string))
                s_pos += 1
                s_pos_values.append(
                    fields[field.replace('"', "")].to_db_value(value, self)
                )
            update_values_string = ", ".join(update_values_strings)
            query = string % (
                table_name,
                insert_fields_string,
                insert_values_string,
                conflictive_pks,
                update_values_string,
            )
            await executor.db.execute_insert(query, s_pos_values)
            created = True
        self._saved_in_db = True
        await self._post_save(db, created, update_fields)


class LiteralField(Generic[L], Field[L]):
    """Simple varchar with type-checking additions as Literal-like."""

    indexable = False
    SQL_TYPE = "TEXT"

    class _db_mysql:
        SQL_TYPE = "LONGTEXT"
    class _db_mssql:
        SQL_TYPE = "NVARCHAR(MAX)"
    class _db_oracle:
        SQL_TYPE = "NCLOB"

    def __init__(
        self,
        primary_key: bool | None = None,
        unique: bool = False,
        db_index: bool = False,
        default: L | None = None,
        **kwargs: Any,
    ) -> None:
        if primary_key or kwargs.get('pk'):
            warnings.warn(
                'TextField as PrimaryKey is Deprecated, use CharField instead',
                DeprecationWarning,
                stacklevel=2,
            )
        if unique:
            raise tortoise.ConfigurationError(
                'TextField doesn\'t support unique indexes, consider CharField or another strategy'
            )
        if db_index or kwargs.get('index'):
            raise tortoise.ConfigurationError(
                'TextField can\'t be indexed, consider CharField'
            )
        super().__init__(
            primary_key=primary_key,
            unique=unique,
            db_index=db_index,
            default=default,
            **kwargs,
        )

    @overload
    def __get__(self, instance: None, owner: type[Model]) -> "LiteralField[L]":
        ...

    @overload
    def __get__(self, instance: Model, owner: type[Model]) -> L:
        ...

    def __get__(self, instance: Model | None, owner: type[Model]):
        return super().__get__(instance, owner)
