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

from typing import Any, Generic, TypeVar

from .warns import WarnConfig, Warn
from .warns.types import WarnObject as WarnPayload

from tortoise import Model
from tortoise.fields import Field
from tortoise.fields.data import JsonDumpsFunc, JsonLoadsFunc, JSON_LOADS, JSON_DUMPS
from tortoise.exceptions import FieldError

T = TypeVar("T")


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
