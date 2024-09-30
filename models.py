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

from typing import Any

from _types.fields import WarnsDataField, Array, WarnsField
from _types.warns import WarnConfig

from tortoise import Model as Table
from tortoise.fields import (
    BigIntField as BigInt,
    BooleanField as Boolean,
    TextField as Varchar,
    JSONField as JSON,
    IntField as Integer,
)


# User Table
class User(Table):
    id = BigInt(primary_key=True)
    optedIn = Boolean(default=False)

    class Meta:
        table = "user"


# Guild Table
class Guild(Table):
    id = BigInt(primary_key=True)
    enabled = Boolean(default=True)
    prefix = Varchar(default="!")
    alter = BigInt(null=True)
    allowed_channels = Array[int](null=True)
    allowed_roles = Array[int](null=True)
    allowed_users = Array[int](null=True)
    bypassed_users = Array[int](null=True)
    bypassed_roles = Array[int](null=True)
    user_report = BigInt(null=True)
    staff_report = BigInt(null=True)

    class Meta:
        table = "guild"


# GuildUser Table
class GuildUser(Table):
    guild = BigInt(primary_key=True)
    user = BigInt()
    warns = WarnsField(default={})

    class Meta:
        table = "guilduser"


# VouchsConfig Table
class VouchsConfig(Table):
    id = BigInt(primary_key=True)
    enabled = Boolean(default=False)
    command_like = Boolean(default=True)
    whitelisted_channels = Array[int](default=[])
    multiplier = Integer(default=1)

    class Meta:
        table = "vouchsconfig"


# VouchGuildUser Table
class VouchGuildUser(Table):
    guild = BigInt(primary_key=True)
    user = BigInt()
    vouchs = BigInt(default=0)
    recent = Array[str](default=[])

    class Meta:
        table = "vouchguilduser"


# WarnsConfig Table
class WarnsConfig(Table):
    id = BigInt(
        primary_key=True,
    )
    enabled = Boolean(default=False)
    config: WarnConfig = WarnsDataField(default=WarnConfig.empty())  # type: ignore
    notifications = BigInt(null=True)

    class Meta:
        table = "warnsconfig"


# GuildApplication Table
class GuildApplication(Table):
    guild = BigInt(primary_key=True)
    name = Varchar()
    questions = Array[dict[str, Any]](default=[])
    permissions = BigInt(default=0)

    class Meta:
        table = "guildapplication"


# StrikeGuildStaff Table
class StrikeGuildStaff(Table):
    guild = BigInt(primary_key=True)
    user = BigInt()
    total_strikes = Integer(default=0)
    strikes: dict[str, Any] = JSON(default={})

    class Meta:
        table = "strikeguildstaff"


# EconomyConfig Table
class EconomyConfig(Table):
    id = BigInt(
        primary_key=True,
    )
    enabled = Boolean(default=True)
    currency = Varchar(default="€")
    work_responses = Array[str](
        default=["Has trabajado duro y has ganado {currency}{money}"]
    )
    public_stats = Boolean(default=False)
    rob_responses: dict[str, list[str]] = JSON(
        default={
            "0": [
                "¡Has intentado robar a {robbed}, pero te pillaron y te multaron por {amount}!"
            ],
            "1": ["¡Has robado {amount} a {robbed}!"],
        }
    )

    class Meta:
        table = "economyconfig"


# EconomyGuildUser Table
class EconomyGuildUser(Table):
    guild = BigInt(primary_key=True)
    user = BigInt()
    money = BigInt(default=0)
    bank = BigInt(default=0)

    class Meta:
        table = "economyguilduser"


# UserTagsPrivate Table
class UserTagsPrivate(Table):
    id = BigInt(
        primary_key=True,
    )
    tags: dict[str, Any] | None = JSON(null=True, default=None)

    class Meta:
        table = "usertagsprivate"


# BubuMissionsGuild Table
class BubuMissionsGuild(Table):
    guild = BigInt(
        primary_key=True,
    )

    class Meta:
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

    class Meta:
        table = "suggestionsconfig"


# Suggestion Table
class Suggestion(Table):
    id = BigInt(primary_key=True)
    voted_users = Array[int](default=[])

    class Meta:
        table = "suggestionmessage"


# Future feature
# class Giveaway(Table):
#    message = BigInt(primary_key=True)  # message ID are unique anyways :shrug:
#    guild = BigInt(null=False)
#    channel = BigInt(null=False)
#    prize = Varchar(null=False)
#    winner_amount = BigInt()
#    duration = BigInt()
#    ended = Boolean(default=False)
#    start = Timestamp()
#    end = Timestamp(null=True)
#    winners = Array(base_column=BigInt(), default=[])
#    host = BigInt(null=False)

#    class Meta:
#        table = "giveaway"
