from __future__ import annotations

import typing
import discord
from discord.ext.commands.flags import FlagConverter, flag
from discord.ext.commands.converter import RoleConverter


class AddStockFlags(FlagConverter):
    category: str = flag(
        name="category",
        aliases=["cat"],
        description="La categoría a la que añadir el stock",
        default="Default",
    )
    stock: str = flag(name="stock", description="El stock que añadir")


class GuildSafetyFlags(FlagConverter):
    timedout: bool = flag(name="timedout", aliases=["out", "to"], default=True)
    unusual_dms: bool = flag(
        name="unusal-dms", aliases=["dms", "unusual-dm"], default=True
    )
    roles: tuple = flag(converter=RoleConverter, aliases=["role"], default=tuple())
    users: tuple = flag(converter=RoleConverter, aliases=["user"], default=tuple())


class RemoveVouchFlags(FlagConverter, prefix="--", delimiter=" "):
    user: discord.Member = flag(positional=True, name="user")
    remove_recent: bool = flag(aliases=["rr"], default=True)
