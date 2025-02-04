from __future__ import annotations
from typing import TYPE_CHECKING

from .core import Musica

if TYPE_CHECKING:
    from _types.bot import Bot

async def setup(bot: Bot) -> None:
    await bot.add_cog(Musica(bot))
