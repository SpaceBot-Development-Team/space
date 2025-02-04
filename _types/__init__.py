from .context import Context, GuildContext, ModGuildContext
from .bot import Bot
from .commands import command, group
from .views import ConfigView, SelectUserWarning, EditPlayer, EmbedBuilderView
from .embeds import AlterRole as AlterRoleEmbed
from . import abc, flags, warns, errors, fields
from .interactions import *
from .queue import *


async def edit_player(ctx: Context, player) -> None:
    await ctx.reply(view=EditPlayer(ctx.author, player))


__all__ = (
    "Context",
    "GuildContext",
    "ModGuildContext",
    "Bot",
    "command",
    "group",
    "ConfigView",
    "AlterRoleEmbed",
    "abc",
    "EmbedBuilderView",
    "SelectUserWarning",
    "EditPlayer",
    "flags",
    "warns",
    "edit_player",
    "GuildInteraction",
    "DMInteraction",
    "PrivateChannelInteraction",
    "errors",
    "fields",
    "Queue",
)
