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

from functools import partial
from typing import Any

from _types.fields import (
    WarnsDataField,
    WarnsField,
    CompositePrimaryKeyTable,
    composite_primary_keys,
)
from _types.warns import WarnConfig

from tortoise import Model as Table
from tortoise.fields import (
    BigIntField as BigInt,
    BooleanField as Boolean,
    TextField as Varchar,
    JSONField as JSON,
    IntField as Integer,
    Field,
)
from tortoise.contrib.postgres.fields import ArrayField as Array

BigIntArray: partial[Field[list[int]]] = partial(Array, 'bigint')
VarcharArray: partial[Field[list[str]]] = partial(Array, 'char')
JSONBArray: partial[Field[dict[str, Any] | list[Any]]] = partial(Array, 'jsonb')

__all__ = (
    'User',
    'Guild',
    'GuildUser',
    'VouchsConfig',
    'VouchGuildUser',
    'WarnsConfig',
    'GuildApplication',
    'StrikeGuildStaff',
    'UserTagsPrivate',
    'BubuMissionsGuild',
    'SuggestionsConfig',
    'Suggestion',
)


# User Table
class User(Table):
    id = BigInt(primary_key=True)
    optedIn = Boolean(default=False)

    class Meta:  # type: ignore
        table = "user"


# Guild Table
class Guild(Table):
    id = BigInt(primary_key=True)
    enabled = Boolean(default=True)
    prefix = Varchar(default="!")
    alter = BigInt(null=True)
    allowed_channels = BigIntArray(null=True)
    allowed_roles = BigIntArray(null=True)
    allowed_users = BigIntArray(null=True)
    bypassed_users = BigIntArray(null=True)
    bypassed_roles = BigIntArray(null=True)
    user_report = BigInt(null=True)
    staff_report = BigInt(null=True)
    locale = Varchar(default='es-ES', null=False)

    class Meta:  # type: ignore
        table = "guild"


# GuildUser Table
@composite_primary_keys("guild", "user")
class GuildUser(CompositePrimaryKeyTable):
    guild = BigInt()
    user = BigInt()
    warns = WarnsField(default={})

    class Meta:  # type: ignore
        table = "guilduser"


# VouchsConfig Table
class VouchsConfig(Table):
    id = BigInt(primary_key=True)
    enabled = Boolean(default=False)
    command_like = Boolean(default=True)
    whitelisted_channels = BigIntArray(default=[])
    multiplier = Integer(default=1)

    class Meta:  # type: ignore
        table = "vouchsconfig"


# VouchGuildUser Table
@composite_primary_keys("guild", "user")
class VouchGuildUser(CompositePrimaryKeyTable):
    guild = BigInt()
    user = BigInt()
    vouchs = BigInt(default=0)
    recent = VarcharArray(default=[])

    class Meta:  # type: ignore
        table = "vouchguilduser"


# WarnsConfig Table
class WarnsConfig(Table):
    id = BigInt(
        primary_key=True,
    )
    enabled = Boolean(default=False)
    config: Field[WarnConfig] = WarnsDataField(default=WarnConfig.empty())  # type: ignore
    notifications = BigInt(null=True)

    class Meta:  # type: ignore
        table = "warnsconfig"


# GuildApplication Table
@composite_primary_keys("guild", "name")
class GuildApplication(CompositePrimaryKeyTable):
    guild = BigInt()
    name = Varchar()
    questions = JSONBArray(default=[])
    permissions = BigInt(default=0)

    class Meta:  # type: ignore
        table = "guildapplication"


# StrikeGuildStaff Table
@composite_primary_keys("guild", "user")
class StrikeGuildStaff(CompositePrimaryKeyTable):
    guild = BigInt()
    user = BigInt()
    total_strikes = Integer(default=0)
    strikes: Field[dict[str, Any]] = JSON(default={})  # type: ignore

    class Meta:  # type: ignore
        table = "strikeguildstaff"


# UserTagsPrivate Table
class UserTagsPrivate(Table):
    id = BigInt(
        primary_key=True,
    )
    tags: Field[dict[str, Any] | None] = JSON(null=True, default=None)  # type: ignore

    class Meta:  # type: ignore
        table = "usertagsprivate"


# BubuMissionsGuild Table
class BubuMissionsGuild(Table):
    guild = BigInt(
        primary_key=True,
    )

    class Meta:  # type: ignore
        table = "bubumissionsguild"


# SuggestionsConfig Table
class SuggestionsConfig(Table):
    id = BigInt(primary_key=True)
    enabled = Boolean(default=False)
    review_channel = BigInt(null=True)
    review_enabled = Boolean(default=True)
    suggestions_channel = BigInt(null=True)
    command_like = Boolean(default=False)
    staff_role = BigInt(null=True)
    allow_selfvote = Boolean(default=True)

    class Meta:  # type: ignore
        table = "suggestionsconfig"


# Suggestion Table
class Suggestion(Table):
    id = BigInt(primary_key=True)
    voted_users = Array(default=[])

    class Meta:  # type: ignore
        table = "suggestionmessage"
