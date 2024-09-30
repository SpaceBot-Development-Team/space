"""
Comandos instalables para los usuarios
"""

from .tags import Tags
from .fun import Fun


async def setup(bot) -> None:
    await bot.add_cog(Tags(bot))
    await bot.add_cog(Fun(bot))
