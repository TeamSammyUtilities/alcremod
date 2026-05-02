import discord

from discord import Embed
from discord.ext import commands
from helpers import checks, constants, interface
from tinydb import Query


class Basic(commands.Cog):
    """Basic bot commands."""
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

    @commands.hybrid_group(aliases=("prefixes",), fallback="list")
    @commands.guild_only()
    async def prefix(self, ctx: commands.Context):
        """Check the bot's available prefixes"""
        Guild = Query()
        guild = self.bot.database.guilds.get(Guild.id == ctx.guild.id) or {}
               
        embed_color = guild.get("color", constants.DEFAULT_COLOR)
        prefixes = guild.get("prefixes", [])
        
        embed = Embed(
            color=embed_color
        )

        embed.add_field(
            name="Available Prefixes",
            value="\n".join(f"{p}" for p in prefixes),
            inline=False
        )

        await ctx.send(embed=embed)

    @prefix.command()
    @commands.guild_only()
    @checks.is_manager()
    async def add(self, ctx: commands.Context, prefix: str):
        """Add a prefix in the custom prefix list.
        
        Manager role is needed to use this command."""
        Guild = Query()
        guild = self.bot.database.guilds.get(Guild.id == ctx.guild.id) or {}
        
        prefixes = guild.get("prefixes", [])
        
        if prefix in prefixes:
            return await ctx.send(f"`{prefix}` has already been added!")
            
        prefixes.append(prefix)
        
        self.bot.database.guilds.upsert(
            {**guild, "id": ctx.guild.id, "prefixes": prefixes},
            Guild.id == ctx.guild.id
        )
        
        await ctx.send(f"`{prefix}` has been added to the custom prefix list.")

    @prefix.command()
    @commands.guild_only()
    @checks.is_manager()
    async def remove(self, ctx: commands.Context, prefix: str):
        """Remove a prefix in the custom prefix list.
        
        Manager role is needed to use this command."""
        Guild = Query()
        guild = self.bot.database.guilds.get(Guild.id == ctx.guild.id) or {}
        
        prefixes = guild.get("prefixes", [])
        
        if not (prefix in prefixes):
            return await ctx.send(f"`{prefix}` not found!")
            
        prefixes.remove(prefix)
        
        self.bot.database.guilds.upsert(
            {**guild, "id": ctx.guild.id, "prefixes": prefixes},
            Guild.id == ctx.guild.id
        )
        
        await ctx.send(f"`{prefix}` has been removed from the custom prefix list.")

#    @commands.hybrid_command()
#    async def stats(self, ctx: commands.Context):
#        """Stats about the bot."""
#        page = interface.Page(
#        )

#        view = interface.Paginator([page])
#        embed = view.get_embed()
        
#        await ctx.send(embed=embed)
        
    @commands.hybrid_command()
    async def ping(self, ctx: commands.Context):
        """Bot latency."""
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"Pong! **{latency} ms**")

    @commands.hybrid_command()
    async def falcio(self, ctx: commands.Context):
        """Specially for Falcio."""
        from datetime import datetime
        embed = discord.Embed(
            title="Level 14 Litleo",
            color=0x9CCFFF
        )
        embed.add_field(
            name="Details",
            value=(
                "**XP:** 0/600"
                "\n**Nature:** Serious"
                "\n**Gender:** Female"
            ),
            inline=True
        )
        embed.add_field(
            name="Stats",
            value=(
                "**HP:** 42 – IV: 1/31"
                "\n**Attack:** 23 – IV: 28/31"
                "\n**Defense:** 25 – IV: 27/31"
                "\n**Sp. Atk:** 28 – IV: 14/31"
                "\n**Sp. Def:** 25 – IV: 30/31"
                "\n**Speed:** 27 – IV: 15/31"
                "\n**Total IV:** 61.83%"
            ),
            inline=True
        )
        embed.set_footer(text=(
            "Displaying pokémon 36423."
            "\nID | 69f08eb84c060f686ffe8739"
            "\nCaught"
        ))
        embed.set_thumbnail(url="https://cdn.discordapp.com/avatars/1430914683883491419/09cdd0235eca17954a0d097cd8bcf17c.png?size=1024")
        embed.set_image(url="https://cdn.poketwo.net/images/667.png")
        embed.timestamp = datetime.fromtimestamp(1777372856)
        await ctx.send(embed=embed)
        

async def setup(bot):
    await bot.add_cog(Basic(bot))