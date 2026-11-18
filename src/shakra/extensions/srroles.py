from discord import Interaction, Member, Role
from discord.app_commands import (
    Group,
    command,
    default_permissions,
    describe,
    guild_only,
)
from discord.ext.commands import Cog
from discord.ui import Modal
from speedruncompy import GetSearch, GetUserSummary, NetworkId
from speedruncompy.datatypes.defs import UserSocialConnection
from speedruncompy.exceptions import NotFound

from .. import Shakra
from ..models import SrRoleEntry
from ..utils import GUILD_IDS, ConfirmationModal


async def setup(bot: Shakra):
    GUILDS = [g for g in (bot.get_guild(id) for id in GUILD_IDS) if g is not None]
    
    await bot.add_cog(SpeedrunRolesCog(bot), guilds=GUILDS)
    bot.tree.add_command(SpeedrunRolesCog.ManageSrRoles(), guilds=GUILDS)

@guild_only()
class SpeedrunRolesCog(Cog):
    bot: Shakra
    
    def __init__(self, bot: Shakra) -> None:
        self.bot = bot
        self.logger = bot.logger.getChild("SrRoles")

    @default_permissions(manage_roles=True)
    class ManageSrRoles(Group, name="sr_roles_manage"):
        @command()
        async def add(self, interaction: Interaction, role: Role, game: str):
            gameSearch = await GetSearch(game, favorExactMatches=True, includeGames=True).perform()
            if (len(gameSearch.gameList) == 0):
                return await interaction.followup.send(f"No game with name `{game}` found!")
            g = gameSearch.gameList[0]
            
            async def addGame(interaction: Interaction):
                await SrRoleEntry.create(guild_id=interaction.guild_id, role_id=role.id, game_id=g.id)
                await interaction.response.send_message(f"Added link for <@&{role.id}> to `{g.name}`", ephemeral=True)
            
            await interaction.response.send_modal(ConfirmationModal(
                addGame, title="Add SR Role", 
                description=f"Allow verified runners of `{g.name}` to claim the role <@&{role.id}>?"))
        
        @command()
        async def remove(self, interaction: Interaction, role: Role):
            count = await SrRoleEntry.filter(guild_id=interaction.guild_id, role_id=role.id).delete()
            await interaction.response.send_message(f"Removed {count} entries for <@&{role.id}>", ephemeral=True)
        
        @command()
        async def list(self, interaction: Interaction):
            role_entries = await SrRoleEntry.filter(guild_id=interaction.guild_id)
            role_strs = [f"<@&{entry.role_id}>: {entry.game_id}" for entry in role_entries]
            
            await interaction.response.send_message(f"## Defined roles:\n{'\n'.join(role_strs)}")
    
    @command()
    @describe(src_username="Your username on Speedrun.com.")
    async def sr_roles(self, interaction: Interaction, src_username: str):
        """Get Speedrun.com-linked roles you are eligible for.
        """
        assert interaction.guild is not None
        assert isinstance(interaction.user, Member)
        
        sr_role_entries = await SrRoleEntry.filter(guild_id=interaction.guild_id)
        if len(sr_role_entries) == 0:
            return await interaction.response.send_message("This server has no SRC-linked roles set up!", ephemeral=True)
        
        try:
            u_summary = await GetUserSummary(src_username).perform()
        except NotFound:
            return await interaction.response.send_message(f"No Speedrun.com user found with username `{src_username}`", ephemeral=True)

        discord_connection: UserSocialConnection | None = next((c for c in u_summary.userSocialConnectionList if c.networkId == NetworkId.DISCORD), None)
        if discord_connection is None or discord_connection.value != interaction.user.name:
            return await interaction.response.send_message(
                f"Could not connect your Discord & Speedrun.com profile!\nEnsure your linked Discord username at [__your settings page__](<https://www.speedrun.com/users/{u_summary.user.url}/settings/socials>) matches your username (`{interaction.user.name}`)"
            )
        
        games = [g.gameId for g in u_summary.userGameRunnerStats]
        allowed_roles: list[Role] = []
        for entry in sr_role_entries:
            if entry.game_id in games:
                role = interaction.guild.get_role(entry.role_id)
                if role is None:
                    self.logger.warning(f"Role {entry.role_id}")
                    await entry.delete()
                    continue
                allowed_roles.append(role)

        await interaction.user.add_roles(*allowed_roles, reason="SrRoles grant")
        await interaction.response.send_message(f"You have been given the roles: {', '.join(f'<@&{r.id}>' for r in allowed_roles)}", ephemeral=True)

class RoleSelectionModal(Modal):
    def __init__(self, roles: list[Role]):
        super().__init__(title="Select Colour Role")



