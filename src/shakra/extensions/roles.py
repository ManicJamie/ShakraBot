from typing import TYPE_CHECKING

import discord
from discord import (
    ButtonStyle,
    Interaction,
    Role,
)
from discord.app_commands import allowed_contexts, allowed_installs, default_permissions
from discord.app_commands import command as slash_cmd
from discord.ext.commands import GroupCog
from discord.ui import (
    ActionRow,
    Button,
    LayoutView,
    Section,
    Select,
)

from ..utils import GUILD_IDS

if TYPE_CHECKING:
    from .. import Shakra

async def setup(bot: Shakra):
    GUILDS = [g for g in (bot.get_guild(id) for id in GUILD_IDS) if g is not None]
    
    await bot.add_cog(RoleCog(bot), guilds=GUILDS)



class RoleButton(Button):
    role: Role
    
    def __init__(self, role: Role, *, style: ButtonStyle = ButtonStyle.primary, label: str | None = None, disabled: bool = False, custom_id: str | None = None, url: str | None = None, emoji: str | discord.Emoji | discord.PartialEmoji | None = None, row: int | None = None, sku_id: int | None = None, id: int | None = None):
        self.role = role
        super().__init__(style=style, label=label, disabled=disabled, custom_id=custom_id, url=url, emoji=emoji, row=row, sku_id=sku_id, id=id)
        
    async def callback(self, interaction: Interaction):
        ...

class RoleSubSelect(Select):
    def __init__(self, roles: list[Role], custom_id: str, placeholder: str, min_values: int, max_values: int, *, required: bool = False) -> None:
        self.roles = roles
        
        options = []
        
        super().__init__(custom_id=custom_id, placeholder=placeholder, min_values=min_values, max_values=max_values, options=options, disabled=False, required=required, row=None)



@default_permissions()
class RoleCog(GroupCog, name="roles"):
    bot: Shakra
    
    def __init__(self, bot: Shakra) -> None:
        self.bot = bot
        
    @slash_cmd(name="test")
    @allowed_contexts(guilds=True)
    @allowed_installs(guilds=True)
    async def role_select_test(self, interaction: Interaction):
        await interaction.response.send_message(view=Tester(), ephemeral=True)
    
    @slash_cmd(name="add_selector")
    @allowed_contexts(guilds=True)
    @allowed_installs(guilds=True)
    async def add_role_selector(self, interaction: Interaction, message_id: int):  # TODO: Write custom transformer
        ...
    

class Tester(LayoutView):
    def __init__(self, *, timeout: float | None = 180) -> None:
        super().__init__(timeout=timeout)
        
        for i in range(13):
            section = Section(*[str("a" * 20)], accessory=Button(label="Press!"))
            self.add_item(section)
        
    
class RoleRow(LayoutView):
    row: ActionRow

    def __init__(self, *, timeout: float | None = None) -> None:
        
        super().__init__(timeout=timeout)
