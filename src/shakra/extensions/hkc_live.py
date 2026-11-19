import os

from discord import AllowedMentions, Forbidden, Game, Interaction, Role, Streaming
from discord.app_commands import command, default_permissions, guild_only
from discord.ext.commands import GroupCog
from discord.ext.tasks import loop
from discord.member import Member
from twitchAPI.helper import first
from twitchAPI.twitch import Twitch

from shakra.config import CONFIG
from shakra.models import HKCLiveRole

from .. import Shakra
from ..utils import APP_NAME, is_bot_owner


async def setup(bot: Shakra):
    APPID = os.environ.get("TWITCH_APPID")
    SECRET = os.environ.get("TWITCH_SECRET")
    
    if APPID is None or SECRET is None:
        bot.logger.info("No Twitch API credentials, not loading hkc_live...")
        return
    
    twitch: Twitch = await Twitch(APPID, SECRET)
    
    await bot.add_cog(HKCLiveCog(bot, twitch))

@guild_only()
@default_permissions(manage_channels=True)
class HKCLiveCog(GroupCog, name="hkc_live"):
    def __init__(self,
        bot: Shakra,
        twitch: Twitch
    ):
        self.bot = bot
        self.logger = bot.logger.getChild("hkc_live")
        self.twitch = twitch
    
    async def cog_load(self):
        self.check_hkc.start()
    
    async def cog_unload(self):
        self.check_hkc.cancel()
        await self.twitch.close()
    
    @command()
    @is_bot_owner
    async def set_channel(self, interaction: Interaction, username: str):
        """Set the twitch channel to track as the bots' live channel. Bot owner only.

        Args:
            username (int): Username of the twitch channel to track.
        """
        user = await first(self.twitch.get_users(logins=[username]))
        if user is None:
            await interaction.response.send_message(f"Could not find Twitch user with name {username}", ephemeral=True)
            return
        CONFIG.live_channel_id = user.id
        CONFIG.persist()
        await interaction.response.send_message(
            f"Updated tracked channel to {user.display_name}!", ephemeral=True
        )
    
    @command()
    async def set_role(self, interaction: Interaction, role: Role | None):
        """Set the role given to the bot when live.

        Args:
            role (Role): Role granted when live.
        """
        if role is None:
            record = await HKCLiveRole.get_or_none(guild_id=interaction.guild_id)
            if record is not None:
                await record.delete()
            await interaction.response.send_message("Live tracking role removed.", ephemeral=True)
            return

        if not role.is_assignable():
            await interaction.response.send_message(
                f"Cannot assign role <@&{role.id}>; make sure this role is assignable!",
                ephemeral=True,
            )
            return

        await HKCLiveRole.update_or_create({"role_id": role.id}, guild_id=interaction.guild_id)
        await interaction.response.send_message(f"Updated HKC live to role <@&{role.id}>", ephemeral=True, allowed_mentions=AllowedMentions.none())
    
    @loop(minutes=1)
    async def check_hkc(self):
        try:
            if CONFIG.live_channel_id is None: return
            
            stream = await first(self.twitch.get_streams(user_id=[CONFIG.live_channel_id], stream_type="live"))
            was_streaming = isinstance(self.bot.activity, Streaming)
            
            if stream is None:
                if was_streaming:
                    await self.bot.change_presence(activity=Game(name="Silksong: Sea of Sorrow"))
                    async for r in HKCLiveRole.all():
                        guild = self.bot.get_guild(r.guild_id)
                        if guild is None: continue
                        role = guild.get_role(r.role_id)
                        if role is None: continue
                        member: Member = guild.get_member(self.bot.own_id)  # ty: ignore[invalid-assignment]
                        if role in member.roles:
                            await member.remove_roles(role, reason=f"{APP_NAME}: going offline")
            else:
                await self.bot.change_presence(activity=Streaming(
                    name="Twitch", 
                    details=stream.title, 
                    url=f"https://twitch.tv/{stream.user_name.lower()}", 
                    state=stream.game_name, 
                    assets={"large_image": f"twitch:{stream.user_name}"}
                    ))

                async for r in HKCLiveRole.all():
                    guild = self.bot.get_guild(r.guild_id)
                    if guild is None:
                        continue
                    role = guild.get_role(r.role_id)
                    if role is None:
                        continue
                    member: Member = guild.get_member(self.bot.own_id)  # ty: ignore[invalid-assignment]
                    if role not in member.roles:
                        try:
                            await member.add_roles(role, reason=f"{APP_NAME}: going live")
                        except Forbidden:
                            self.logger.error("Cannot manage this role!")
        except Exception as e:
            self.logger.error("check_hkc failed! Ignoring:", exc_info=e)