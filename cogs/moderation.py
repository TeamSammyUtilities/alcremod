import discord

from datetime import datetime, timezone, timedelta
from discord.ext import commands, tasks
from enum import Enum
from helpers import checks, converters, interface
from tinydb import Query
from typing import NamedTuple, Optional


class CaseType(Enum):
    WARN = "Warning"
    MUTE = "Mute"
    KICK = "Kick"
    BAN = "Ban"


class Case(NamedTuple):
    id: int
    type: str
    reason: str
    offender: int
    moderator: int
    timestamp: int


class Moderation(commands.Cog):
    """For moderation commands."""
    def __init__(self, bot):
        self.bot = bot
        self.version = "0.1.1"
        self.snipe_cache = {}

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

    async def create_case(self, guild_id: int, type: CaseType, reason: str, offender: discord.Member, moderator: discord.Member) -> Case:
        Guild = Query()
        guild = self.bot.database.guilds.get(Guild.id == guild_id)

        if guild is None:
            guild = {}

        case_counter = guild.get("case_counter", 0) + 1
        cases = guild.get("cases", [])

        case = Case(
            id=case_counter,
            type=type.value,
            reason=reason,
            offender=offender.id,
            moderator=moderator.id,
            timestamp=int(datetime.now(timezone.utc).timestamp())
        )

        cases.append(case._asdict())

        self.bot.database.guilds.upsert(
            {
                **guild,
                "id": guild_id,
                "case_counter": case_counter,
                "cases": cases
            },
            Guild.id == guild_id
        )

        return case

    async def get_case(self, guild_id: int, case_id: int) -> Case | None:
        Guild = Query()
        guild = self.bot.database.guilds.get(Guild.id == guild_id)

        if guild is None:
            return None

        for case in guild.get("cases", []):
            if case_id == case["id"]:
                return Case(
                     **{**case, "type": CaseType(case["type"])}
                )
        return None

    async def get_color(self, guild_id: int):
        Guild = Query()
        guild = self.bot.database.guilds.get(Guild.id == guild_id) or {}
            
        return guild.get("color", constant.DEFAULT_COLOR)

    @tasks.loop(seconds=30)
    async def mute_task(self):
        now = int(datetime.now(timezone.utc).timestamp())

        Guild = Query()
        all_guilds = self.bot.database.guilds.all()

        for guild_data in all_guilds:
            mutes = guild_data.get("mutes", [])
            if not mutes:
                continue

            guild = self.bot.get_guild(guild_data["id"])
            if guild is None:
                continue

            mute_role = discord.utils.get(guild.roles, name="Muted")
            if mute_role is None:
                continue

            updated_mutes = []

            for mute in mutes:
                if mute["unmute_at"] <= now:
                    member = guild.get_member(mute["user_id"])

                    if member:
                       await member.remove_roles(mute_role, reason="Mute expired")
                       await self.bot.dm_user(
                           f"You have been unmuted in **{guild.name}**."
                       )
                else:
                    updated_mutes.append(mute)

            self.bot.database.guilds.upsert(
                {**guild_data, "mutes": updated_mutes},
                Guild.id == guild.id
            )

    @tasks.loop(seconds=60)
    async def ban_task(self):
        now = int(datetime.now(timezone.utc).timestamp())

        Guild = Query()
        all_guilds = self.bot.database.guilds.all()

        for guild_data in all_guilds:
            bans = guild_data.get("bans", [])
            if not bans:
                continue

            guild = self.bot.get_guild(guild_data["id"])
            if guild is None:
                continue

            updated_bans = []

            for ban in bans:
                if ban["unban_at"] <= now:
                    user_id = ban["user_id"]

                    try:
                        user = await self.bot.fetch_user(user_id)
                        await guild.unban(user, reason="Tempban expired")
                    except:
                        pass
                else:
                    updated_bans.append(ban)

            self.bot.database.guilds.upsert(
                {**guild_data, "bans": updated_bans},
                Guild.id == guild.id
            )

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot:
            return

        cache = self.snipe_cache.setdefault(message.channel.id, [])

        cache.insert(0, {
            "content": message.content,
            "author": message.author,
            "time": datetime.now(timezone.utc)
        })

        self.snipe_cache[message.channel.id] = cache[:10]

    @commands.hybrid_command()
    @commands.guild_only()
    @checks.is_manager()
    async def warn(self, ctx: commands.Context, user: discord.Member, reason: str):
        """Warn a user with a reason.
        
        Manager role is needed to use this command."""
        case = await self.create_case(
            ctx.guild.id,
            CaseType.WARN,
            reason,
            user,
            ctx.author
        )

        page = interface.Page(
            title="You have been Warned!",
            description=f"{user.mention} has been warned in **{ctx.guild.name}**.",
            color=await self.get_color(ctx.guild.id),
            fields=[
                {"name": "Reason", "value": reason, "inline": False},
                {"name": "Case ID", "value": str(case.id), "inline": True},
                {"name": "Moderator", "value": ctx.author.mention, "inline": True}
            ]
        )

        view = interface.Paginator([page])
        embed = view.get_embed()

        await self.bot.dm_user(user, embed=embed)
        await ctx.send(embed=embed)

    @commands.hybrid_command()
    @commands.guild_only()
    @checks.is_manager()
    async def mute(self, ctx: commands.Context, user: discord.Member, duration: str, reason: str):
        """Mute a user with a reason.
        
        Manager role is needed to use this command."""
        if user == ctx.author:
            return await ctx.send("You cannot mute yourself.")

        if user.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send("You cannot mute this user due to role hierarchy.")

        if not ctx.guild.me.guild_permissions.manage_roles:
            return await ctx.send("I do not have permission to manage roles.")

        try:
            seconds = converters.parse_duration(duration)
        except ValueError:
            return await ctx.send("Invalid duration format. Example: `10m`, `2.5h`, `1h30m`")

        mute_role = discord.utils.get(ctx.guild.roles, name="Muted")

        if mute_role is None:
            mute_role = await ctx.guild.create_role(name="Muted")

            for channel in ctx.guild.channels:
                await channel.set_permissions(mute_role, send_messages=False, speak=False)

        await user.add_roles(mute_role, reason=reason)

        unmute_at = int(datetime.now(timezone.utc).timestamp()) + seconds

        Guild = Query()
        guild = self.bot.database.guilds.get(Guild.id == ctx.guild.id) or {}

        mutes = guild.get("mutes", [])
        mutes.append({
            "user_id": user.id,
            "unmute_at": unmute_at,
            "reason": reason
        })

        self.bot.database.guilds.upsert(
            {**guild, "id": ctx.guild.id, "mutes": mutes},
            Guild.id == ctx.guild.id
        )

        case = await self.create_case(
            ctx.guild.id,
            CaseType.MUTE,
            f"{reason} | Duration: {duration}",
            user,
            ctx.author
        )

        page = interface.Page(
            title="User Muted",
            description=f"{user.mention} has been muted in **{ctx.guild.name}**.",
            color=await self.get_color(ctx.guild.id),
            fields=[
                {"name": "Reason", "value": reason, "inline": False},
                {"name": "Duration", "value": duration, "inline": True},
                {"name": "Case ID", "value": str(case.id), "inline": True},
                {"name": "Moderator", "value": ctx.author.mention, "inline": True}
            ]
        )

        view = interface.Paginator([page])
        embed = view.get_embed()

        await self.bot.dm_user(user, embed=embed)
        await ctx.send(embed=embed)

    @commands.hybrid_command()
    @commands.guild_only()
    @checks.is_manager()
    async def kick(self, ctx: commands.Context, user: discord.Member, reason: str):
        """Kick a user with a reason.
        
        Manager role is needed to use this command."""
        if user == ctx.author:
            return await ctx.send("You cannot kick yourself! =3")

        if user.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send("You cannot kick this user due to role hierarchy!")

        if not ctx.guild.me.guild_permissions.kick_members:
            return await ctx.send("I do not have permission to kick members!")

        await user.kick(reason=reason)

        case = await self.create_case(
            ctx.guild.id,
            CaseType.KICK,
            reason,
            user,
            ctx.author
        )

        page = interface.Page(
            title="User Kicked",
            description=f"{user.mention} has been kicked from **{ctx.guild.name}**.",
            color=await self.get_color(ctx.guild.id),
            fields=[
                {"name": "Reason", "value": reason, "inline": False},
                {"name": "Case ID", "value": str(case.id), "inline": True},
                {"name": "Moderator", "value": ctx.author.mention, "inline": True}
            ]
        )

        view = interface.Paginator([page])
        embed = view.get_embed()

        await self.bot.dm_user(user, embed=embed)
        await ctx.send(embed=embed)

    @commands.hybrid_command()
    @commands.guild_only()
    @checks.is_manager()
    async def ban(self, ctx: commands.Context, user: discord.Member, duration: str, reason: str):
        """Ban a user with a reason.
        
        Manager role is needed to use this command."""
        if user == ctx.author:
            return await ctx.send("You cannot ban yourself.")

        if user.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send("You cannot ban this user due to role hierarchy.")

        if not ctx.guild.me.guild_permissions.ban_members:
            return await ctx.send("I do not have permission to ban members.")

        if duration == "0":
            seconds = 0
        else:
            try:
                seconds = converters.parse_duration(duration)
            except ValueError:
                return await ctx.send("Invalid duration. Example: `10m`, `2h`, `1h30m`, or `0` for permanent.")

        page = interface.Page(
            title="You have been Banned",
            description=f"You were banned from **{ctx.guild.name}**.",
            color=await self.get_color(ctx.guild.id),
            fields=[
                {"name": "Reason", "value": reason, "inline": False},
                {"name": "Duration", "value": "Permanent" if seconds == 0 else duration, "inline": True},
                {"name": "Moderator", "value": ctx.author.mention, "inline": True}
            ]
        )

        view = interface.Paginator([page])
        embed = view.get_embed()

        await self.bot.dm_user(user, embed=embed)
        await ctx.guild.ban(user, reason=reason, delete_message_days=0)

        case = await self.create_case(
            ctx.guild.id,
            CaseType.BAN,
            f"{reason} | Duration: {'Permanent' if seconds == 0 else duration}",
            user,
            ctx.author
        )

        if seconds > 0:
            unban_at = int(datetime.now(timezone.utc).timestamp()) + seconds

            Guild = Query()
            guild = self.bot.database.guilds.get(Guild.id == ctx.guild.id) or {}

            bans = guild.get("bans", [])
            bans.append({
                "user_id": user.id,
                "unban_at": unban_at,
                "reason": reason
            })

            self.bot.database.guilds.upsert(
                {**guild, "id": ctx.guild.id, "bans": bans},
                Guild.id == ctx.guild.id
            )

        await ctx.send(embed=embed)

    @commands.hybrid_command()
    @commands.guild_only()
    @checks.is_manager()
    async def unmute(self, ctx: commands.Context, user: discord.Member, reason: str):
        """Unmute a user with a reason.
        
        Manager role is needed to use this command."""
        mute_role = discord.utils.get(ctx.guild.roles, name="Muted")

        if mute_role is None:
            return await ctx.send("Muted role does not exist.")

        if mute_role not in user.roles:
            return await ctx.send("User is not muted.")

        await user.remove_roles(mute_role, reason=reason)

        Guild = Query()
        guild = self.bot.database.guilds.get(Guild.id == ctx.guild.id) or {}

        mutes = guild.get("mutes", [])
        mutes = [m for m in mutes if m["user_id"] != user.id]

        self.bot.database.guilds.upsert(
            {**guild, "id": ctx.guild.id, "mutes": mutes},
            Guild.id == ctx.guild.id
        )

        case = await self.create_case(
            ctx.guild.id,
            CaseType.MUTE,
            f"Manual unmute | {reason}",
            user,
            ctx.author
        )

        await ctx.send(f"{user.mention} has been unmuted. Case #{case.id}")


    @commands.hybrid_command()
    @commands.guild_only()
    @checks.is_manager()
    async def unban(self, ctx: commands.Context, user_id: int, reason: str):
        """Unban user with a reason.
        
        Manager role is needed to use this command."""
        user = await self.bot.fetch_user(user_id)

        try:
            await ctx.guild.unban(user, reason=reason)
        except discord.NotFound:
            return await ctx.send("User is not banned.")

        Guild = Query()
        guild = self.bot.database.guilds.get(Guild.id == ctx.guild.id) or {}

        bans = guild.get("bans", [])
        bans = [b for b in bans if b["user_id"] != user_id]

        self.bot.database.guilds.upsert(
            {**guild, "id": ctx.guild.id, "bans": bans},
            Guild.id == ctx.guild.id
        )

        case = await self.create_case(
            ctx.guild.id,
            CaseType.BAN,
            f"Manual unban | {reason}",
            user,
            ctx.author
        )

        await ctx.send(f"{user} has been unbanned. Case #{case.id}")

    @commands.hybrid_command()
    @commands.guild_only()
    @checks.is_manager()
    async def history(self, ctx: commands.Context, user: discord.Member):
        """Show a user history logs.
        
        Manager role is needed to use this command."""
        Guild = Query()
        guild = self.bot.database.guilds.get(Guild.id == ctx.guild.id)

        if not guild:
            return await ctx.send("No history found.")

        cases = guild.get("cases", [])
        user_cases = [c for c in cases if c["offender"] == user.id]

        if not user_cases:
            return await ctx.send("No cases found for this user.")

        embed = discord.Embed(
            title=f"Case History - {user}",
            color=0xEEBEBA
        )

        for c in user_cases[-10:]:
            embed.add_field(
                name=f"Case #{c['id']} ({c['type']})",
                value=f"{c['reason']}",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.hybrid_command()
    @commands.guild_only()
    @checks.is_manager()
    async def case(self, ctx: commands.Context, case_id: int):
        """Show a specific case
        
        Manager role is needed to use this command."""
        case = await self.get_case(ctx.guild.id, case_id)

        if not case:
            return await ctx.send("Case not found.")

        embed = discord.Embed(
            title=f"Case #{case.id}",
            color=0xEEBEBA,
            description=f"**Type:** {case.type}\n**Reason:** {case.reason}"
        )

        embed.add_field(name="Offender", value=f"<@{case.offender}>", inline=True)
        embed.add_field(name="Moderator", value=f"<@{case.moderator}>", inline=True)
        embed.add_field(name="Timestamp", value=str(case.timestamp), inline=False)

        await ctx.send(embed=embed)

    @commands.hybrid_command()
    @commands.guild_only()
    @checks.is_manager()
    async def lock(self, ctx: commands.Context, channel: discord.TextChannel = None, reason: str = "No reason provided"):
        """Lock the channel selected.
        
        Manager role is needed to use this command."""
        channel = channel or ctx.channel

        overwrites = channel.overwrites_for(ctx.guild.default_role)
        overwrites.send_messages = False

        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrites, reason=reason)

        await ctx.send(f"{channel.mention} has been locked.\nReason: {reason}.")

    @commands.hybrid_command()
    @commands.guild_only()
    @checks.is_manager()
    async def unlock(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Unlock the channel selected.
        
        Manager role is needed to use this command."""
        channel = channel or ctx.channel

        overwrites = channel.overwrites_for(ctx.guild.default_role)
        overwrites.send_messages = None

        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrites)

        await ctx.send(f"{channel.mention} has been unlocked.")

    @commands.hybrid_command()
    @commands.guild_only()
    @checks.is_manager()
    async def purge(self, ctx: commands.Context, user: discord.Member, duration: str):
        """Purge specific messages from a member.
        
        Manager role is needed to use this command."""
        try:
            seconds = converters.parse_duration(duration)
        except ValueError:
            return await ctx.send("Invalid duration. Example: `10m`, `2h`, `1h30m`")

        cutoff = datetime.now(timezone.utc) - timedelta(seconds=seconds)

        deleted = 0

        for channel in ctx.guild.text_channels:
            try:
                async for message in channel.history(limit=1000, after=cutoff):
                    if message.author.id == user.id:
                        try:
                            await message.delete()
                            deleted += 1
                        except discord.HTTPException:
                            pass
            except discord.Forbidden:
                continue

        await ctx.send(f"Deleted {deleted} messages from {user.mention} in the last {duration}.")

    @commands.hybrid_command()
    @commands.guild_only()
    @checks.is_manager()
    async def snipe(self, ctx: commands.Context, index: int = 1, channel: discord.TextChannel = None):
        """Snipe a deleted message.
        
        Manager role is needed to use this command."""
        channel = channel or ctx.channel
        cache = self.snipe_cache.get(channel.id, [])

        if not cache:
            return await ctx.send("Nothing to snipe.")

        if index < 1 or index > len(cache):
            return await ctx.send(f"Invalid index. Range: 1-{len(cache)}")

        data = cache[index - 1]

        embed = discord.Embed(
            description=data["content"] or "*No text content*",
            color=0xEEBEBA
        )

        embed.set_author(name=str(data["author"]), icon_url=data["author"].display_avatar.url)
        embed.set_footer(text=f"Snipe #{index} • {data['time'].strftime('%H:%M:%S UTC')}")

        await ctx.send(embed=embed)

    async def cog_load(self):
        self.mute_task.start()
        self.ban_task.start()


async def setup(bot):
    await bot.add_cog(Moderation(bot))