from __future__ import annotations

from typing import TYPE_CHECKING, Any, Coroutine, Generator, Literal
import discord
import asyncio
import copy
import time
import traceback
import sys
import logging
import importlib
import os

from jishaku.paginators import PaginatorEmbedInterface
from discord.ext.commands.cog import Cog
from discord.ext import commands
from _types import Context, Bot


if TYPE_CHECKING:
    from typing_extensions import Self

logger = logging.getLogger(__name__)


class PerfMocker:
    def __init__(self) -> None:
        self.loop = asyncio.get_running_loop()

    def permissions_for(self, obj: Any) -> discord.Permissions:
        perms = discord.Permissions.all()
        perms.administrator = False
        perms.embed_links = False
        perms.add_reactions = False
        return perms

    def __getattr__(self, attr: str) -> Self:
        return self

    def __call__(self, *args: Any, **kwargs: Any) -> Self:
        return self

    def __repr__(self) -> str:
        return "<PerfMocker>"

    def __await__(self) -> Generator[Any, None, Self]:
        future: asyncio.Future[Self] = self.loop.create_future()
        future.set_result(self)
        return future.__await__()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: Any) -> Self:
        return self

    def __len__(self) -> Literal[0]:
        return 0

    def __bool__(self) -> Literal[False]:
        return False


class Owner(Cog, command_attrs=dict(hidden=True)):
    def __init__(self, bot: Bot) -> None:
        self.bot: Bot = bot

    def cog_check(self, ctx: Context) -> Coroutine[Any, Any, bool]:
        return self.bot.is_owner(ctx.author)

    @commands.command(name="bot-servers", hidden=True)
    @commands.is_owner()
    async def _bot_servers(self, ctx: Context) -> None:
        base_paginator = commands.Paginator(
            None,
            None,
        )
        base_paginator.add_line(
            (
                f"**Cantidad de servidores:** {len(self.bot.guilds)}\n"
                "~~~~~~~~~~~~~~~~~~~~~~~~~~"
            )
        )

        for guild in self.bot.guilds:
            base_paginator.add_line(
                (
                    f"**Nombre:** {guild.name}\n"
                    f"**Dueño:** <@{guild.owner_id}> ({guild.owner_id})\n"
                    f"**Miembros:** {guild.member_count or guild.approximate_member_count}\n"
                    "--------------------"
                )
            )

        paginator = PaginatorEmbedInterface(
            bot=self.bot,
            paginator=base_paginator,
            owner=ctx.author,
            delete_message=True,
            embed=discord.Embed(color=self.bot.default_color),
        )
        await paginator.send_to(ctx.channel)

    @commands.command(hidden=True)
    async def perf(self, ctx: Context, *, command: str) -> None:
        """Calcula el rendimiento de un comando, intentando suprimir todas las peticiones HTTP y a la DB"""

        message: discord.Message = copy.copy(ctx.message)
        message.content = ctx.prefix + command

        new_ctx = await self.bot.get_context(message, cls=type(ctx))
        new_ctx._state = PerfMocker()  # type: ignore
        new_ctx.channel = PerfMocker()  # type: ignore

        if new_ctx.command is None:
            await ctx.reply("No command found")
            return

        start = time.perf_counter()
        try:
            await new_ctx.command.invoke(new_ctx)
        except commands.CommandError:
            end = time.perf_counter()
            success = False
            try:
                await ctx.reply(f"```py\n{traceback.format_exc()}\n```")
            except discord.HTTPException:
                pass
        else:
            end = time.perf_counter()
            success = True

        await ctx.reply(
            f"Status: {ctx.tick(success)} Tiempo de ejecución: {(end-start) * 1000:.2f}ms"
        )

    IMPORT_STRINGS = (
        "from {} import",
        "import {}",
        "__import__({}",
        "from .{} import",
        "import .{}",
    )

    def _resolve_relative_import(self, path: str, rel_import: str) -> str:
        """Converts a relative import (i.e.: from .warns on the cogs folder) to an absolute import
        based of the file path where the import has occurred.
        """
        dir = os.path.dirname(path)
        base_module = dir.replace(os.sep, ".").lstrip(".")
        return f"{base_module}.{rel_import}"

    def _reload_module_and_importers(
        self, module_name: str, search_path: str = "."
    ) -> None:
        """Reloads a module and every file in the local machine that import it.
        Handles relative imports.
        """

        module = __import__(module_name)
        importlib.reload(module)

        for root, _, files in os.walk(search_path):
            for file in files:
                if not file.endswith(".py"):
                    continue
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as file_buffer:
                        content = file_buffer.read().replace("\n", " ")
                        found_import = False
                        # This constant is True if the file imports, in any way, the module
                        # that was reloaded.

                        for import_string in self.IMPORT_STRINGS:
                            if import_string.format(module_name) in content:
                                found_import = True
                                break
                            if f'.{module_name.split(".")[-1]}' in content:
                                rel = module_name.split(".")[-1]
                                abs = self._resolve_relative_import(file_path, rel)
                                if abs in sys.modules:
                                    found_import = True
                                    break

                        if found_import:
                            rel_path = os.path.relpath(file_path, search_path)
                            mod_name_from_file = os.path.splitext(rel_path.replace(os.sep, "."))[0]
                            if mod_name_from_file in sys.modules:
                                logger.debug(
                                    'Reloaded module %s for total reload of %s',
                                    mod_name_from_file,
                                    module_name,
                                )
                                importlib.reload(sys.modules[mod_name_from_file])
                except Exception as exc:
                    logger.error(
                        'Error occurred while reloading module %s for total reload of %s. Traceback:\n%s',
                        file_path,
                        module_name,
                        traceback.format_exception(
                            type(exc), exc, exc.__traceback__,
                        ),
                    )
                    raise exc
        logger.info('Successfully reloaded module %s and all files that import it', module_name)

    @discord.utils.copy_doc(_reload_module_and_importers)
    async def reload_module_and_importers(
        self, module_name: str, search_path: str = "."
    ) -> None:
        return await self.bot.loop.run_in_executor(
            None, self._reload_module_and_importers, module_name, search_path
        )

    @commands.command(hidden=True)
    async def hotreload(self, ctx: Context, *, module: str) -> None:
        """Recarga un módulo, recargando de paso todos los archivos que lo importan."""

        if module.startswith('cogs.') and module in self.bot.extensions.keys():  # Module is a cog, then
            await self.bot.reload_extension(module)
        ret = await ctx.reply(f"Recargando módulo ``{module}``")
        try:
            await self.reload_module_and_importers(module)
        except Exception as exc:
            err = await ctx.safe_send(
                f"Un error ocurrió:\n{traceback.format_exception(type(exc), exc, exc.__traceback__)}"
            )
            await ret.edit(
                content=f"Un error ocurrió, [ve al mensaje de error]({err.jump_url})",
            )
        else:
            await ret.edit(content="¡Recargado exitósamente!",)


async def setup(bot: Bot) -> None:
    await bot.add_cog(Owner(bot))
