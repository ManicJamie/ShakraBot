import asyncio
import importlib
import logging
import logging.handlers
import os
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import discord
import discord.app_commands
from discord import Interaction, User
from discord.abc import Messageable
from discord.app_commands import (
    AppCommandError,
    CommandOnCooldown,
    allowed_contexts,
    allowed_installs,
    guild_install,
    user_install,
)
from discord.app_commands import command as slash_cmd
from discord.ext.commands import (
    Bot,
    Cog,
    Context,
    ExtensionError,
)
from discord.ext.commands import command as text_cmd
from tortoise import Tortoise
from tortoise import connections as TortConnections

from .utils import APP_NAME, GUILD_IDS, is_bot_owner, message_embed

# TODO: Discord.py's Bot system is not fit for purpose, switch to Client & manage cogs/extensions ourselves.

class BaseCog(Cog):
    bot: Shakra
    logger = logging.getLogger('discord.shakra.base')
    
    def __init__(self, bot: Shakra) -> None:
        self.bot = bot
    
    async def cog_load(self) -> None:
        pass
    

class GlobalCog(Cog):
    bot: Shakra
    logger = logging.getLogger('discord.shakra.global')
    
    def __init__(self, bot: Shakra) -> None:
        self.bot = bot
    
    @slash_cmd(description="Pong!")
    @guild_install()
    async def ping(self, interaction: Interaction):
        delay = (datetime.now(UTC) - interaction.created_at).microseconds // 1000
        await interaction.response.send_message(f"pong! ({delay}ms)")
    
    @slash_cmd(description="Get a user's avatar.")
    @allowed_installs(guilds=True, users=True)
    @allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def avatar(self, interaction: Interaction, user: User, private: bool = True):
        await interaction.response.send_message(
            content=user.display_avatar.url,
            ephemeral=private)
    
    @text_cmd(name="avatar", description="Get a user's avatar.")
    async def avatar_text(self, context: Context, user: User):
        await context.reply(content=user.display_avatar.url, mention_author=False)
        
    async def _reload_cogs(self) -> dict[str, ExtensionError | None]:
        errored_exts: dict[str, None | ExtensionError] = {}
        for ext in list(self.bot.extensions.keys()):
            self.logger.info(f"Extension '{ext}' reloading...")
            try:
                await self.bot.reload_extension(ext)
                errored_exts[ext] = None
                self.logger.info(f"Extension '{ext}' reloaded!")
            except ExtensionError as e:
                errored_exts[ext] = e
                self.logger.error(f"Extension '{ext}' failed to reload, reverting...", exc_info=e)
        self.logger.info("Syncing trees")
        await self.bot.tree.sync()
        GUILDS = [g for g in (self.bot.get_guild(id) for id in GUILD_IDS) if g is not None]
        await self.bot.tree.sync(guild=GUILDS[0])
        self.logger.info("Trees synced")
        return errored_exts
    
    @slash_cmd(description=f"Reload {APP_NAME}'s modules. Only available to the owner.")
    @user_install
    @allowed_contexts(dms=True)
    @is_bot_owner
    async def reload_extensions(self, interaction: Interaction):
        await interaction.response.defer()
        exts = await self._reload_cogs()
        outstr = "\n".join(e if out is None else f"{e} FAILED: {out.__repr__()}" for e, out in exts.items())
        await interaction.followup.send(embed=message_embed(title="Reloaded extensions", description=outstr))


EXT_FOLDER = Path(__file__).with_name("extensions")

def get_extension_names() -> list[str]:
    return [
        fpath.with_suffix("").name 
        for fpath in EXT_FOLDER.glob("*")
        if (fpath.suffix == ".py" or fpath.is_dir()) and (not fpath.name.startswith("__"))
    ]

class Shakra(Bot):
    logger = logging.getLogger('discord.shakra')
    cmd_failure_handlers: list[Callable[..., Coroutine[Any, Any, bool]]]
    """List of failure handlers to invoke before processing a command as an error."""
    
    __shakra_cogs: dict[str, Cog]
    """Cogs to be registered to guilds. Global commands will be registered everywhere;
    per-guild commands will be registered to the guilds defined."""
    
    async def on_ready(self):
        self.cmd_failure_handlers = []
        self.logger.info(f"Logged in as {self.user}")
        guild = self.get_guild(GUILD_IDS[0])
        
        await self.add_cog(GlobalCog(self))
        await self.add_cog(BaseCog(self), guild=guild)
        
        for ext in get_extension_names():
            try:
                await self.load_extension(f".extensions.{ext}", package="shakra")
            except ExtensionError as e:
                self.logger.error(e)
        
        self.logger.info("Syncing trees...")
        await self.tree.sync(guild=guild)
        await self.tree.sync()
        self.logger.info("Synced tree")
    
    async def get_messageable_safe(self, channel_id: int) -> Messageable | None:
        """Get a messageable channel, first from cache and if not in cache then fetch.
        
        NB: CategoryChannel is not abc.Messageable!"""
        if isinstance(channel := self.get_channel(channel_id), Messageable): return channel
        if channel is not None:
            self.logger.warning(f"Channel {channel_id} is not Messageable, guarding...")
            return None
        self.logger.debug(f"Channel {channel_id} not in cache, fetching...")
        
        try:
            if not isinstance(channel := await self.fetch_channel(channel_id), Messageable):
                self.logger.warning(f"Channel {channel_id} is not Messageable, guarding...")
                return None
            self.logger.debug("Successfully fetched!")
        except Exception as e:
            self.logger.error("Reacted channel couldn't be fetched!", exc_info=e)
            return None
        else:
            return channel
    
    async def register_cog(self, cog: Cog):
        """Register a cog to the bot. Does NOT sync trees - see """
    
    async def sync_cogs(self):
        ...
    
    async def deregister_cog(self, cog: Cog):
        """Deregister a cog from the bot. Does NOT sync trees."""
    
    async def on_interaction_error(self, interaction: Interaction, error: AppCommandError):
        if isinstance(error, CommandOnCooldown):
            return await interaction.response.send_message(f"Command is on cooldown; retry after {error.retry_after:0.}s.")
        
        self.logger.error(error, exc_info=error)
        return await interaction.response.send_message(embed=message_embed(
            title=f"Unhandled exception in {APP_NAME}!",
            description=f"```{str(error.__repr__())[:4090]}```",
            fields=[("", "If this message doesn't help, consider reporting to <@196347053100630016>", False)]
        ))

def get_models():
    for mod in [".", *[f".extensions.{name}" for name in get_extension_names()]]:
        importlib.import_module(mod, "shakra")

TORT_CONFIG = {
    "connections": {
        "default": {
            "engine": "tortoise.backends.sqlite",
            "credentials": {
                "file_path": "db.sqlite3",
                "journal_mode": "DELETE"
            }
        }
    },
    "apps": {
        "models": {
            "models": ["shakra.models"],
            "default_connection": "default"
        }
    }
}

async def hook():
    discord.utils.setup_logging(root=True)
    
    if not os.path.exists("./logs"): os.mkdir("./logs")
    fileHandler = logging.handlers.TimedRotatingFileHandler(
        filename="logs/shakra.log",
        encoding="utf-8",
        when="midnight",
        backupCount=7,
        utc=True
    )
    fileHandler.setFormatter(logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', '%Y-%m-%d %H:%M:%S', style='{'))
    logging.getLogger().addHandler(fileHandler)
    
    
    await Tortoise.init(
        config=TORT_CONFIG
    )
    await Tortoise.generate_schemas()  # TODO: make robust
    
    intents = discord.Intents.default()
    
    client = Shakra(";", intents=intents)
    try:
        async with client:
            await client.start(os.environ["TOKEN"])
    finally:
        await TortConnections.close_all()
    

def main() -> None:
    asyncio.run(hook())
    

if __name__ == "__main__":
    main()