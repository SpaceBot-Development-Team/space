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

import inspect
import itertools
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import commands, menus

from paginator import Paginator

if TYPE_CHECKING:
    from bot import LegacyBotContext as Context, LegacyBot


class GroupHelpPageSource(menus.ListPageSource):
    def __init__(
        self,
        group: commands.Group | commands.Cog,
        entries: list[commands.HybridCommand],
        *,
        prefix: str,
    ) -> None:
        super().__init__(entries=entries, per_page=6)

        self.group: commands.Group | commands.Cog = group
        self.prefix: str = prefix
        self.title: str = f"Commands in `{self.group.qualified_name}`"
        self.description: str = self.group.description

    async def format_page(self, menu: Paginator, commands: list[commands.HybridCommand]) -> discord.Embed:  # type: ignore
        embed = discord.Embed(
            title=self.title,
            description=self.description,
            colour=discord.Colour.blurple(),
        )

        for command in commands:
            signature = f"{PaginatedHelpCommand.get_usage_emojis(command)} {command.qualified_name} {command.signature}"
            embed.add_field(
                name=signature,
                value=command.short_doc or "No short help",
                inline=False,
            )

        maximum = self.get_max_pages()

        if maximum > 1:
            embed.set_author(name=f"Page {menu.current_page + 1}/{maximum} ({len(self.entries)} commands)")

        embed.set_footer(text=f'Use "{self.prefix}help <command>" for more information on a command.')
        return embed


class HelpSelectMenu(discord.ui.Select["HelpMenu"]):
    def __init__(self, entries: dict[commands.Cog, list[commands.HybridCommand]], bot: LegacyBot):
        super().__init__(
            placeholder="Choose a category...",
            min_values=1,
            max_values=1,
            row=0,
        )
        self.commands: dict[commands.Cog, list[commands.HybridCommand]] = entries
        self.bot: LegacyBot = bot
        self.__fill_options()

    def __fill_options(self) -> None:
        self.add_option(
            label="Index",
            emoji="👋",
            value="__index",
            description="Main bot help page",
        )
        for cog, cmds in self.commands.items():
            if not cmds:
                continue
            description = cog.description.split("\n", 1)[0] or None
            emoji = getattr(cog, "display_emoji", None)
            self.add_option(
                label=cog.qualified_name,
                value=cog.qualified_name,
                description=description,
                emoji=emoji,
            )

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        value = self.values[0]
        if value == "__index":
            await self.view.rebind(FrontPageSource(), interaction)
        else:
            cog = self.bot.get_cog(value)
            if cog is None:
                await interaction.response.send_message("This category somehow does not exist!", ephemeral=True)
                return

            commands = self.commands[cog]
            if not commands:
                await interaction.response.send_message(
                    "This category has no usable commands!",
                    ephemeral=True,
                )
                return

            source = GroupHelpPageSource(cog, commands, prefix=self.view.ctx.clean_prefix)
            await self.view.rebind(source, interaction)


class FrontPageSource(menus.PageSource):
    def is_paginating(self) -> bool:
        # This forces the buttons to appear even in the front page
        return True

    def get_max_pages(self) -> int | None:
        # There's only one actual page in the front page
        # However we need at least 2 to show all the buttons
        return 2

    async def get_page(self, page_number: int) -> Any:
        # The front page is a dummy
        self.index = page_number
        return self

    def format_page(self, menu: HelpMenu, page: Any):
        embed = discord.Embed(title="Bot Help", colour=discord.Colour.blurple())
        embed.description = inspect.cleandoc(
            f"""
            Hey! Welcome to the help page!

            Use "{menu.ctx.clean_prefix}help <command>" for more information on a command.
            Use "{menu.ctx.clean_prefix}help <category>" for more information on a category.
            Use the select below to choose any category.
        """
        )

        embed.add_field(
            name="Support Server",
            value="If you need help or have any questions regarding the bot, join our support server!: https://discord.gg/m9UsWuaYDT",
            inline=False,
        )

        created_at = discord.utils.format_dt(menu.ctx.bot.user.created_at, "F")  # type: ignore
        if self.index == 0:
            embed.add_field(
                name="Who are you?",
                value=(
                    "I'm a bot made by `@dev_anony`. I am a multi-usage-multi-tool bot with complete feature-packed giveaways!"
                    f"I have been here since {created_at}. To obtain more information on my features, check the select below!"
                ),
                inline=False,
            )
        elif self.index == 1:
            entries = (
                (
                    "The emoji commands",
                    "If the command name is prefixed with <:prefixed_command:1293248180606996600>, you can use it as a prefix command "
                    f"(`{menu.ctx.prefix}<command_name>`), if it is prefixed with <:application_command:1293248219266027591> "
                    "you can use it as an slash command (`/<command_name>`).",
                ),
                (
                    "<argument>",
                    "This indicates that the argument is __**required**__.",
                ),
                ("[argument]", "This indicates that the argument is __**optional**__."),
                (
                    "[A|B]",
                    "This indicates that the argument can be __**any of A or B**__.",
                ),
                (
                    "[argument...]",
                    "This indicates that you can pass multiple values to this argument.\n"
                    "And now that you know the basics... You should also know...\n"
                    "__**You don't write the `()`, `[]`, `|` or `<>` when using a command!**__",
                ),
            )

            embed.add_field(
                name="How do I use this bot?",
                value="Reading a command syntax is pretty simple.",
            )

            for name, value in entries:
                embed.add_field(name=name, value=value, inline=False)

        return embed


class HelpMenu(Paginator):
    def __init__(self, source: menus.PageSource, ctx: Context):
        super().__init__(source, context=ctx, compact=True)

    def add_categories(self, commands: dict[commands.Cog, list[commands.HybridCommand]]) -> None:
        self.clear_items()
        self.add_item(HelpSelectMenu(commands, self.ctx.bot))
        self.fill_items()

    async def rebind(self, source: menus.PageSource, interaction: discord.Interaction) -> None:
        self.source = source
        self.current_page = 0

        await self.source._prepare_once()
        page = await self.source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(0)
        await interaction.response.edit_message(**kwargs, view=self)


class PaginatedHelpCommand(commands.HelpCommand):
    context: Context  # type: ignore
    with_app_command: bool = True

    def __init__(self):
        super().__init__(
            command_attrs={
                "cooldown": commands.CooldownMapping.from_cooldown(1, 3.0, commands.BucketType.member),
                "help": "Shows a command, group or category help",
            }
        )

    async def on_help_command_error(self, ctx: Context, error: commands.CommandError):  # type: ignore
        if isinstance(error, commands.CommandInvokeError):
            # Ignore missing permission errors
            if isinstance(error.original, discord.HTTPException) and error.original.code == 50013:
                return

            await ctx.send(str(error.original))

    def get_command_signature(self, command: commands.HybridCommand) -> str:  # type: ignore
        parent = command.full_parent_name
        if len(command.aliases) > 0:
            aliases = "|".join(command.aliases)
            fmt = f"[{command.name}|{aliases}]"
            if parent:
                fmt = f"{parent} {fmt}"
            alias = fmt
        else:
            alias = command.name if not parent else f"{parent} {command.name}"
        return f"{self.get_usage_emojis(command)} {alias} {command.signature}"

    async def send_bot_help(self, mapping: dict):
        bot = self.context.bot

        def key(command: commands.HybridCommand) -> str:
            cog = command.cog
            return cog.qualified_name if cog else "\U0010ffff"

        entries: list[commands.HybridCommand] = await self.filter_commands(  # type: ignore
            bot.commands,
            sort=True,
            key=key,  # type: ignore
        )

        all_commands: dict[commands.Cog, list[commands.HybridCommand]] = {}
        for name, children in itertools.groupby(entries, key=key):
            if name == "\U0010ffff":
                continue

            cog = bot.get_cog(name)
            assert cog is not None
            all_commands[cog] = sorted(children, key=lambda c: c.qualified_name)

        menu = HelpMenu(FrontPageSource(), ctx=self.context)
        menu.add_categories(all_commands)
        await menu.start(content=None)

    async def send_cog_help(self, cog):
        entries = await self.filter_commands(cog.get_commands(), sort=True)
        menu = HelpMenu(
            GroupHelpPageSource(cog, entries, prefix=self.context.clean_prefix),  # type: ignore
            ctx=self.context,
        )
        await menu.start(content=None)

    @staticmethod
    def get_usage_emojis(command: commands.HybridCommand | commands.HybridGroup) -> str:
        application_emoji = "<:application_command:1293248219266027591>"
        string = "<:prefixed_command:1293248180606996600>"
        if not isinstance(command, commands.HybridCommand):
            match type(command):
                case commands.Command:
                    return string
                case discord.app_commands.Command:
                    return application_emoji
                case (
                    commands.help._HelpCommandImpl,
                    commands.HelpCommand,
                    commands.MinimalHelpCommand,
                    commands.DefaultHelpCommand,
                ):
                    return string + application_emoji
        if not hasattr(command, "with_app_command"):
            return string
        if command.with_app_command and command.app_command:
            string += application_emoji
        return string

    def common_command_formatting(
        self,
        embed_like: discord.Embed,
        command: commands.HybridCommand | commands.HybridGroup,
    ):
        embed_like.title = self.get_command_signature(command)  # type: ignore
        if command.description:
            embed_like.description = f"{command.description}\n\n{command.help}"
        else:
            embed_like.description = command.help or "No short help"

    async def send_command_help(self, command: commands.HybridCommand | commands.HybridGroup):  # type: ignore
        # No pagination necessary for a single command.
        embed = discord.Embed(colour=discord.Colour.blurple())
        self.common_command_formatting(embed, command)
        await self.context.send(content=None, embed=embed)

    async def send_group_help(self, group: commands.HybridGroup):  # type: ignore
        subcommands = group.commands
        if len(subcommands) == 0:
            return await self.send_command_help(group)

        entries = await self.filter_commands(subcommands, sort=True)
        if len(entries) == 0:
            return await self.send_command_help(group)

        source = GroupHelpPageSource(group, entries, prefix=self.context.clean_prefix)  # type: ignore
        self.common_command_formatting(source, group)  # type: ignore
        menu = HelpMenu(source, ctx=self.context)
        await menu.start(content=None)


class ShowVarsView(discord.ui.View):
    def __init__(self, author: discord.abc.User) -> None:
        self.author: discord.abc.User = author
        self.message: discord.Message | None = None
        super().__init__(timeout=60 * 15)

    def enable_all(self) -> None:
        for child in self.children:
            if hasattr(child, 'disabled'):
                child.disabled = False  # pyright: ignore[reportAttributeAccessIssue]
            if hasattr(child, 'style'):
                child.style = discord.ButtonStyle.blurple  # pyright: ignore[reportAttributeAccessIssue]

    async def on_timeout(self) -> None:
        if self.message:
            await self.message.edit(view=None)

    def get_win_message_variables_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title='Win Message Variables',
            description='These variables can be used to format your win message and spice it up!',
            colour=discord.Colour.blurple(),
        )

        embed.add_field(
            name='\u200b',
            value='- `{claim_time}` - The amount of seconds the winner (e.g.: 10 seconds)\n'
            '- `{host(username)}` - The giveaway host username (e.g.: '
            f'{self.author.name})\n'
            '- `{host(mention)}` - The giveaway host mention (e.g.: '
            f'{self.author.mention})\n'
            '- `{winner(username)}` - The giveaway winner username (e.g.: '
            f'{self.author.name})\n'
            '- `{winner(mention)}` - The giveaway winner mention (e.g.: '
            f'{self.author.mention})\n'
            '- `{winner(created_ago)}` - When was the winner account created, in relative (e.g.: `2 years ago`)\n'
            '- `{winner(created_date)}` - When was the winner account created, in full date (e.g.: `17 May 2016 22:57`)\n'
            '- `{winner(joined_ago)}` - When the winner joined the server, in relative (e.g.: `3 months ago`)\n'
            '- `{winner(joined_date)}` - When the winner joined the server, in full date (e.g.: `20 May 2016 11:43`)',
        )
        return embed

    def get_gw_embed_variables_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title='Giveaway Embed Variables',
            description='These variables can be used to format your giveaway embed and spice it up!',
            colour=discord.Colour.blurple(),
        )

        embed.add_field(
            name='\u200b',
            value='- `{prize}` - The giveaway prize\n'
            '- `{host(username)}` - The giveaway host username (e.g: '
            f'{self.author.name})\n'
            '- `{host(mention)}` - The giveaway host mention (e.g.: '
            f'{self.author.mention})\n'
            '- `{time_left}` - The remaining time until the giveaway ends, or how much time ended (e.g.: `in 10 minutes`/`10 minutes ago`)\n'
            '- `{end_time}` - The date when the giveaway will end (e.g.: `Tuesday, 17 May 2016 22:57`)\n'
            '- `{num_winners}` - The amount of winners of the giveaway (e.g.: `1`)\n'
            '- `{ends}` - `Ends` if the giveaway has not ended, `Ended` when so. This is usually mixed as `{ends} {time_left}` to obtain results such'
            ' as `Ends in 10 minutes` or `Ended 10 minutes ago`.\n'
            '- `{server_name}` - The server name.\n'
            '- `{winner_list}` - The giveaway winners, or `Not decided` if they have not yet been decided.\n'
            '- `{winners}` - It will work as `{num_winners}` if the giveaway has not ended and no winners are decided, when winners are decided, '
            'it works as `{winner_list}`.',
        )
        return embed

    def get_greet_message_variables_embed(self, server_name: str) -> discord.Embed:
        embed = discord.Embed(
            title='Greet Message Variables',
            description='These variables can be used to format your greet message and spice it up!',
            colour=discord.Colour.blurple(),
        )
        embed.add_field(
            name='\u200b',
            value='- `{mention}` - The member mention (e.g.: '
            f'{self.author.mention})\n'
            '- `{mc}` - The server member count (e.g.: 1)\n'
            '- `{server(name)}` - The server name (e.g.: '
            f'{server_name})\n'
            '- `{member(tag)}` - The member username (e.g: '
            f'{self.author.name})\n'
            '- `{member(name)}` - The member name (e.g.: '
            f'{self.author.display_name})',
        )
        return embed

    @discord.ui.button(label='Win Message Variables', style=discord.ButtonStyle.blurple)
    async def win_message_variables(
        self, interaction: discord.Interaction[LegacyBot], button: discord.ui.Button[ShowVarsView]
    ) -> None:
        self.enable_all()
        button.disabled = True
        button.style = discord.ButtonStyle.grey
        await interaction.response.edit_message(embed=self.get_win_message_variables_embed(), view=self)

    @discord.ui.button(label='Giveaway Embed Variables', style=discord.ButtonStyle.blurple)
    async def gw_embed_variables(
        self, interaction: discord.Interaction[LegacyBot], button: discord.ui.Button[ShowVarsView]
    ) -> None:
        self.enable_all()
        button.disabled = True
        button.style = discord.ButtonStyle.grey
        await interaction.response.edit_message(embed=self.get_gw_embed_variables_embed(), view=self)

    @discord.ui.button(
        label='Greet Message Variables',
        style=discord.ButtonStyle.blurple,
    )
    async def greet_msg_vars(
        self, interaction: discord.Interaction[LegacyBot], button: discord.ui.Button[ShowVarsView]
    ) -> None:
        assert interaction.guild
        self.enable_all()
        button.disabled = True
        button.style = discord.ButtonStyle.grey
        await interaction.response.edit_message(
            embed=self.get_greet_message_variables_embed(interaction.guild.name),
            view=self,
        )

    async def start(self, ctx: Context) -> None:
        self.win_message_variables.disabled = True
        self.win_message_variables.style = discord.ButtonStyle.grey
        self.message = await ctx.reply(
            embed=self.get_win_message_variables_embed(),
            view=self,
        )


class Meta(commands.Cog):
    """Meta commands that are not categorized."""

    display_emoji = '\N{HAMMER AND WRENCH}'

    def __init__(self, bot: LegacyBot) -> None:
        self.paginated_help_command = PaginatedHelpCommand()
        self._previous_help = bot.help_command
        bot.help_command = self.paginated_help_command
        bot.help_command.cog = self

        self.bot: LegacyBot = bot
        self._bot_help_cmd = self.bot.get_command("help")

    @discord.app_commands.command(name="help")
    @discord.app_commands.checks.cooldown(1, 30, key=lambda i: (i.guild_id, i.user.id))
    async def slash_help(self, interaction: discord.Interaction, *, command: str | None = None) -> None:
        """Shows a command, group or category help.

        Parameters
        ----------
        command:
            The command, group, or category to show the help of.
        """
        context = await self.bot.get_context(interaction)
        self.paginated_help_command.context = context
        await self.paginated_help_command.command_callback(context, command=command)

    @commands.hybrid_command(name='variables', aliases=['vars'])
    async def show_vars(self, ctx: Context) -> None:
        """Shows the variables for win messages, and giveaways."""

        await ShowVarsView(ctx.author).start(ctx)


async def setup(bot: LegacyBot) -> None:
    await bot.add_cog(Meta(bot))


async def teardown(bot: LegacyBot) -> None:
    await bot.remove_cog(Meta.__cog_name__)
