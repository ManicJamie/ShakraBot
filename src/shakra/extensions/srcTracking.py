from discord.app_commands import default_permissions, guild_only
from discord.ext.commands import GroupCog

from .. import Shakra
from ..utils import GUILD_IDS


async def setup(bot: Shakra):
    GUILDS = [g for g in (bot.get_guild(id) for id in GUILD_IDS) if g is not None]
    
    await bot.add_cog(SrcTrackingCog(bot), guilds=GUILDS)

@guild_only
@default_permissions()
class SrcTrackingCog(GroupCog, group_name="src_tracking"):
    bot: Shakra
    
    def __init__(self, bot: Shakra) -> None:
        self.bot = bot
        self.logger = bot.logger.getChild("SrcTracking")

