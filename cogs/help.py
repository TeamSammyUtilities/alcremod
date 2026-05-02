import discord

from discord.ext import commands
from helpers import constants, interface
from tinydb import Query
from typing import Optional

HIDDEN_CATEGORY = ["Help", "Jishaku"]


class Help(commands.Cog):
    """For help command."""
    def __init__(self, bot):
        self.bot = bot
        self.version = "0.1.1"

    async def version_control(self):
        if self.bot.version == self.version:
            return

        channel = getattr(self.bot, "logs_channel", None)
        if not channel:
            return

        await channel.send(
            f"Outdated Cog: {self.__class__.__name__} "
            f"(Bot: {self.bot.version} | Cog: {self.version})"
        )

    async def get_color(self, guild_id: int):
        Guild = Query()
        guild = self.bot.database.guilds.get(Guild.id == guild_id) or {}
        return guild.get("color", constants.DEFAULT_COLOR)

    @commands.hybrid_command()
    async def help(self, ctx: commands.Context, *, query: Optional[str] = None):
        """Shows all available commands."""
        color = await self.get_color(ctx.guild.id if ctx.guild else 0)

        if query is None:
            pages = []
            fields = []

            for cog_name, cog in self.bot.cogs.items():
                if cog_name in HIDDEN_CATEGORY:
                    continue

                command_list = [
                    command
                    for command in cog.get_commands()
                    if not command.hidden
                ]

                if not command_list:
                    continue

                formatted_list = " ".join(f"`{command.name}`" for command in command_list)

                fields.append({
                    "name": cog_name,
                    "value": f"{cog.description or 'No description.'}\n{formatted_list}",
                    "inline": False
                })

            if not fields:
                await ctx.send("Nothing found!")
                return

            for i in range(0, len(fields), 3):
                pages.append(
                    interface.Page(
                        title="Help",
                        description=[
                            "Use `?help <command>` for more info on a command.",
                            "Use `?help <category>` for more info on a category."
                        ],
                        color=color,
                        fields=fields[i:i + 3]
                    )
                )

            view = interface.Paginator(pages)
            embed = view.get_embed()

            return await ctx.send(embed=embed, view=view)

        cog = self.bot.get_cog(query)

        if cog:
            command_list = [command for command in cog.get_commands() if not command.hidden]

            page = interface.Page(
                title=cog.qualified_name,
                description=cog.description or "No description.",
                color=color,
                fields=[
                    {
                        "name": command.name,
                        "value": command.help or "No description",
                        "inline": False
                    }
                    for command in command_list
                ]
            )

            view = interface.Paginator([page])
            embed = view.get_embed()

            return await ctx.send(embed=embed)

        command = None

        if query:
            parts = query.split()

            current = self.bot

            for part in parts:
                if isinstance(current, commands.Bot):
                    command = current.get_command(part)
                else:
                    command = current.get_command(part)

                if command is None:
                    break

                current = command

        if command:
            fields = []

            if command.aliases:
                fields.append({
                    "name": "Aliases",
                    "value": ", ".join(command.aliases),
                    "inline": False
                })

            fields.append({
                "name": "Usage",
                "value": f"{command.qualified_name} {command.signature}",
                "inline": False
            })

            subcommands = []

            if isinstance(command, commands.Group):
                subcommands = [command for command in command.commands if not command.hidden]

            if subcommands:
                fields.append({
                    "name": "Subcommands",
                    "value": "\n".join(
                        f"`{command.qualified_name}` - {command.help or 'No description'}"
                        for command in subcommands
                    ),
                    "inline": False
                })

            page = interface.Page(
                title=f"Help: {command.qualified_name}",
                description=command.help or "No description provided.",
                color=color,
                fields=fields
            )

            view = interface.Paginator([page])
            embed = view.get_embed()

            return await ctx.send(embed=embed)
        await ctx.send("Nothing found!")


async def setup(bot):
    await bot.add_cog(Help(bot))