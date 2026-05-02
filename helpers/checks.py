from discord.ext import commands
from tinydb import Query

class NotManager(commands.CheckFailure):
    def __init__(self):
        super().__init__("You do not have 'Manager' permissions!")

def is_manager():
    async def predicate(ctx: commands.Context):
        Guild = Query()
        guild = ctx.bot.database.guilds.get(Guild.id == ctx.guild.id)
        
        if guild is None:
            guild = {}
        
        manager = guild.get("manager", [])
        
        has_role = any(role.id in manager for role in ctx.author.roles)
        has_perm = ctx.author.guild_permissions.manage_guild
        
        if not (has_role or has_perm):
            raise NotManager()
        
        return True
    
    return commands.check(predicate)        