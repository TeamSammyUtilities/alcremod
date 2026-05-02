import cleaner
import dotenv
import discord
import os
import traceback

from discord.ext import commands    
from helpers import constants
from tinydb import Query

dotenv.load_dotenv(".env")


class Bot(commands.Bot):
    def __init__(self):
        super().__init__(
            case_insensitive=True,
            command_prefix=self.get_prefixes,
            help_command=None,
            intents=discord.Intents.all()
        )

        self.version = "0.1.1"

        self.main_guild = None
        self.errors_channel = None
        self.logs_channel = None

        self._ready_once = False
        
    async def get_prefixes(self, bot, message):
        if message.guild is None:
            return constants.DEFAULT_PREFIXES
        
        Guild = Query()
        guild = self.database.guilds.get(Guild.id == message.guild.id) or {}
        
        custom = guild.get("prefixes", [])
        
        return constants.DEFAULT_PREFIXES + custom

    async def is_owner(self, user):
        if user.id in constants.DEVELOPER:
            return True
        return await super().is_owner(user)

    async def setup_hook(self):
        await self.load_extension("jishaku")
        for cog in constants.COGS:
            await self.load_extension(f"cogs.{cog}")

    async def on_ready(self):
        if getattr(self, "_ready_once", False):
            return
        self._ready_once = True

        self.main_guild = self.get_guild(constants.SERVER) or await self.fetch_guild(constant.SERVER)

        if self.main_guild:
            self.errors_channel = self.main_guild.get_channel(constants.ERRORS)
            self.logs_channel = self.main_guild.get_channel(constants.LOGS)

        for cog in self.cogs.values():
            version_control = getattr(cog, "version_control", None)
            if version_control:
                await version_control()

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send(str(error))
            return
        
        if isinstance(error, commands.UserInputError):
            await ctx.send(str(error))
            return

        if isinstance(error, commands.CommandNotFound):
            return

        original = getattr(error, "original", error)

        tb = traceback.extract_tb(original.__traceback__)
        last = tb[-1] if tb else None

        error_type = type(original).__name__
        error_desc = str(original)

        location = (
            f"{last.filename}:{last.lineno} in {last.name}"
            if last else "Unknown location"
        )
        
        messages = [
            f"[COMMAND] {ctx.command}",
            f"[ERROR] {error_type}",
            f"[DESC] {error_desc}",
            f"[LOC] {location}",
        ]
        
        formatted = "\n".join(messages)
        
        print(formatted)

        if self.errors_channel:
            await self.errors_channel.send(formatted)
            
    @property
    def database(self):
        cog = self.get_cog("Database")
        if cog is None:
            raise RuntimeError("Database cog is not loaded yet.")
        return cog

    async def dm_user(self, user, message):
        try:
            await user.send(message)
        except discord.Forbidden:
            pass
    

if __name__ == "__main__":
    bot = Bot()
    bot.run(os.environ["TOKEN"])
    cleaner.clear_pycache(".")