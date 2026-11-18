from typing import TYPE_CHECKING

from discord import (
    BanEntry,
    Guild,
    Interaction,
    NotFound,
)
from discord.app_commands import allowed_contexts
from discord.app_commands import command as slash_cmd
from discord.app_commands.checks import cooldown
from discord.ext.commands import Cog
from discord.ui import ActionRow, Button, LayoutView, Modal

from ...utils import DEV_ID

if TYPE_CHECKING:
    from ... import Shakra
    

    
class BanList(LayoutView):
    def __init__(self, bans: list[tuple[Guild, BanEntry]], *, timeout: float | None = 180) -> None:
        super().__init__(timeout=timeout)
                
        for banGuild, banItem in bans:
            class AppealButton(Button):
                guild = banGuild
                ban = banItem
                def __init__(self, label: str):
                    super().__init__(label=label)
                
                async def callback(self, interaction: Interaction) -> None:
                    await interaction.response.send_modal(AppealModal(self.guild, self.ban))
            
            button = AppealButton(label=f"{banGuild.name}")
            self.add_item(ActionRow(
                button
            ))

class AppealModal(Modal):
    def __init__(self, guild: Guild, ban: BanEntry) -> None:
        self.guild = guild
        self.ban = ban
        super().__init__(title="Appeal")
        
        
    async def on_submit(self, interaction: Interaction) -> None:
        await interaction.response.send_message("meme")

class AppealsCog(Cog):
    def __init__(self, bot: Shakra) -> None:
        self.bot = bot
        super().__init__()
    
    @slash_cmd(name="appeal")
    @cooldown(rate=1, per=30)
    @allowed_contexts(dms=True, guilds=False, private_channels=False)
    async def appeal(self, interaction: Interaction):
        bans: list[tuple[Guild, BanEntry]] = []
        for g in self.bot.guilds:
            try:
                bans.append((g, await g.fetch_ban(interaction.user)))  # ty: ignore[invalid-argument-type]
            except NotFound: 
                continue
        if len(bans) == 0:
            await interaction.response.send_message(f"Couldn't find any bans; if you believe this is in error, please DM <@{DEV_ID}>")
            return
        await interaction.response.send_message(view=BanList(bans))
    
    