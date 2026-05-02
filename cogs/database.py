from discord.ext import commands
from tinydb import TinyDB


class Database(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.version = "0.1.1"
        
        self.database = TinyDB("database.json")
        self.members = self.database.table("members")
        self.users = self.database.table("users")
        self.guilds = self.database.table("guilds")
        self.channels = self.database.table("channels")

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

    async def cog_unload(self):
        self.db.close()


async def setup(bot):
    await bot.add_cog(Database(bot))