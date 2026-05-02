import discord

from datetime import datetime
from discord.ext import commands
from helpers import checks, constants, converters, interface, trackers
from tinydb import Query
from typing import NamedTuple, Optional

MAX_CHAR = 75
THRESHOLD_MESSAGES = 5
THRESHOLD_TIME = 60


class Status(NamedTuple):
    id: int
    status: str
    timestamp: int
    dm: bool


class AFK(commands.Cog):
    """"User Status commands"""
    def __init__(self, bot):
        self.bot = bot
        self.version = "0.1.1"
        
        self.tracker = trackers.MessageTracker(window_seconds=THRESHOLD_TIME)

    async def version_control(self):
        bot_version = getattr(self.bot, "version", None)

        if bot_version == self.version:
            return

        channel = getattr(self.bot, "logs_channel", None)
        if not channel:
            return

        await channel.send(
            f"Outdated Cog: {self.__class__.__name__} "
            f"(Bot: {bot_version} | Cog: {self.version})"
        )

    async def set_status(self, author_id, status):
        User = Query()
        user = self.bot.database.users.get(User.id == author_id) or {}
        
        self.bot.database.users.upsert(
            {
                **user,
                "id": author_id,
                "afk": {
                    "status": status,
                    "timestamp": int(datetime.now().timestamp())
                }
            },
            User.id == author_id
        )

    async def set_config(self, author_id, new_config):
        User = Query()
        user = self.bot.database.users.get(User.id == author_id) or {}
        config = user.get("afk_config", {})

        self.bot.database.users.upsert(
            {**user, "id": author_id, "afk_config": {**config, **new_config}},
            User.id == author_id
        )

    async def set_nickname(self, user_id: int, afk: bool):
        User = Query()
        user = self.bot.database.users.get(User.id == user_id) or {}
        original = user.get("original_nickname")

        for guild in self.bot.guilds:
            member = guild.get_member(user_id)

            if not member:
                continue

            try:
                if afk:
                    current = member.display_name

                    if current.startswith("[AFK] "):
                        continue

                    if not original:
                        original = current

                        self.bot.database.users.upsert(
                            {
                                **user,
                                "id": user_id,
                                "original_nickname": original
                            },
                            User.id == user_id
                        )

                    await member.edit(
                        nick=f"[AFK] {current}"
                    )

                else:
                    if original:
                        await member.edit(
                            nick=original
                        )

            except discord.Forbidden:
                pass
            except discord.HTTPException:
                pass

    async def get_status(self, author_id) -> Status:
        User = Query()
        user = self.bot.database.users.get(User.id == author_id) or {}
        status = user.get("afk", {})
        config = user.get("afk_config", {})
        
        return Status(
            id=author_id,
            status=status.get("status", "Online"),
            timestamp=status.get("timestamp", 0),
            dm=config.get("dm", True)
        )
        
    async def get_color(self, guild_id: int):
        Guild = Query()
        guild = self.bot.database.guilds.get(Guild.id == guild_id) or {}
 
        return guild.get("color", constants.DEFAULT_COLOR)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.display_name == after.display_name:
            return

        User = Query()
        user = self.bot.database.users.get(User.id == after.id) or {}
        afk = user.get("afk")

        if not afk:
            return

        try:
            current = after.display_name

            if not current.startswith("[AFK] "):
                await after.edit(
                    nick=f"[AFK] {current}"
                )

            elif current.startswith("[AFK] [AFK] "):
                fixed = current.replace(
                    "[AFK] [AFK] ",
                    "[AFK] ",
                    1
                )

                await after.edit(
                    nick=fixed
                )

        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None:
            return

        if message.author.bot:
            return
        
        status = await self.get_status(message.author.id)
        
        if status.status != "Online":
            messages = self.tracker.add_message(message.author.id)

            if messages > THRESHOLD_MESSAGES:
                await self.set_status(message.author.id, "Online")
                await self.set_nickname(message.author.id, False)

                duration = int(datetime.now().timestamp()) - status.timestamp

                await message.channel.send(
                    "Welcome back, your status has been cleared. "
                    f"You have been gone for {converters.format_duration(duration)}."
                )

        for member in message.mentions:
            if member.id == message.author.id:
                continue

            perm = message.channel.permissions_for(member)
            if not perm.view_channel:
                continue

            status = await self.get_status(member.id)

            if status.status != "Online":
                await message.channel.send(
                    f"**{member.name}** is currently:\n{status.status}",
                    delete_after=5
                )

                if status.dm:
                    await self.bot.dm_user(
                        member,
                        f"You have been mentioned in {message.channel}.\n"
                        f"Jump To: [message]({message.jump_url})"
                    )

    @commands.hybrid_group()
    async def afk(self, ctx: commands.Context, *, status: str = "AFK"):
        if len(status) > MAX_CHAR:
            return await ctx.send(
                f"Status cannot be over {MAX_CHAR} characters long!"
            )
        
        await self.set_nickname(ctx.author.id, True)
        await self.set_status(ctx.author.id, status)
        await ctx.send(f"Set status to:\n{status}")

    @afk.command()
    async def clear(self, ctx: commands.Context):
        status = await self.get_status(ctx.author.id)
        
        if status.status == "Online":
            return await ctx.send("You are not AFK!")
        
        await self.set_nickname(ctx.author.id, False)
        await self.set_status(ctx.author.id, "Online")
        await ctx.send("Your status has been cleared.")

    @afk.command()
    async def status(self, ctx: commands.Context, user: Optional[discord.User]):
        if user is None:
            user = ctx.author

        status = await self.get_status(user.id)
        color = await self.get_color(ctx.guild.id if ctx.guild else 0)

        value = status.status

        page = interface.Page(
            author={
                "name": "Status",
                "icon_url": user.display_avatar.url
            },
            fields=[{
                "name": "Status",
                "value": value
            }],
            color=color
        )
        
        view = interface.Paginator([page])
        embed = view.get_embed()
        
        await ctx.send(embed=embed)

    @afk.command()
    async def dm(self, ctx: commands.Context):
        status = await self.get_status(ctx.author.id)
        
        await self.set_config(ctx.author.id, {"dm": not status.dm})
        
        if status.dm:
            await ctx.send("You will now not receive a DM when someone mention you.")
        else:
            await ctx.send("You will now receive a DM when someone mention you.")


async def setup(bot):
    await bot.add_cog(AFK(bot))