

from discord import Embed, Interaction, Member, Role
from discord.app_commands import (
    Transform,
    allowed_contexts,
    allowed_installs,
    default_permissions,
)
from discord.app_commands import command as slash_cmd
from discord.ext.commands import GroupCog

from ...models import MuteTier
from ...utils import APP_COLOUR, DurationTransformer


@allowed_contexts(guilds=True)
@allowed_installs(guilds=True)
@default_permissions(mute_members=True)
class ModerationMuteCog(GroupCog, group_name="mute"):
    @slash_cmd(name="tier_add")
    async def tier_add(self, interaction: Interaction, role: Role, label: str):
        tier, created = await MuteTier.update_or_create(defaults=
                                                        {"guild_id": interaction.guild_id,
                                                         "label": label,
                                                         "role_id": role.id}
                                                        )
        
        await interaction.response.send_message(
            embeds=[Embed(color=APP_COLOUR, title="Success!", 
                            description=f"Mute tier {tier.label} {'added' if created else 'updated'} for role <@{tier.role_id}>")])

    @slash_cmd(name="tier_remove")
    async def tier_remove(self, interaction: Interaction, label: str):
        tier = await MuteTier.get_or_none(guild_id=interaction.guild_id, label=label)
        if tier is None:
            await interaction.response.send_message(f"Tier {label} does not exist")
            return
        await tier.delete()
        return await interaction.response.send_message()
        
    @slash_cmd(name="give")
    async def give(self, interaction: Interaction, user: Member, tier: str, duration: Transform[float, DurationTransformer] | None):
        ... # TODO: stub
    
    @slash_cmd(name="remove")
    async def remove(self, interaction: Interaction, user: Member, tier: str):
        ... # TODO: stub
    
    @tier_add.autocomplete("label")
    @tier_remove.autocomplete("label")
    @give.autocomplete("tier")
    @remove.autocomplete("tier")
    async def mute_tier(self, interaction: Interaction, stub: str):
        ... # TODO: stub