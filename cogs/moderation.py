import discord

# ... other imports ...

# Remove suppress import

async def mute_task(member, message):
    try:
        await self.bot.dm_user(member, message)
    except discord.Forbidden:
        pass

async def some_function(user, embed):
    try:
        await self.bot.dm_user(user, embed)
    except (discord.Forbidden, discord.HTTPException):
        pass
