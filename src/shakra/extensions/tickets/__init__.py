import logging
from typing import TYPE_CHECKING

from discord import (
    ForumChannel,
    Guild,
    Interaction,
    PartialEmoji,
    SelectOption,
    TextStyle,
    Thread,
    User,
)
from discord.app_commands import command as slash_cmd
from discord.app_commands import default_permissions, dm_only, guild_only
from discord.ext.commands import Cog, GroupCog
from discord.ui import Label, Modal, Select, TextInput

from ...models import GuildConfig, Ticket
from ...utils import APP_NAME, GUILD_IDS, message_embed

if TYPE_CHECKING:
    from ... import Shakra


async def setup(bot: Shakra):
    GUILDS = [g for g in (bot.get_guild(id) for id in GUILD_IDS) if g is not None]
    
    await bot.add_cog(TicketSubmissionCog(bot))
    await bot.add_cog(TicketReceptionCog(bot), guilds=GUILDS)

class SubmitTicketModal(Modal):
    def __init__(self, guilds: list[Guild]) -> None:
        super().__init__(title="Create ticket", timeout=None, custom_id="ticket_modal")
        
        self.guilds = {g.id: g for g in guilds}
        
        self.guild_select = Select(options=[SelectOption(label=g.name, value=str(g.id)) for g in guilds])
        self.add_item(Label(text="Server", component=self.guild_select))
        self.ticket_input = TextInput(style=TextStyle.long, min_length=1)
        self.add_item(Label(text="Ticket content", component=self.ticket_input))
    
    async def on_submit(self, interaction: Interaction):
        guild_id = int(self.guild_select.values[0])
        text = self.ticket_input.value
        
        gconfig = await GuildConfig.get(guild_id=guild_id)
        if gconfig.ticket_forum_id is None or gconfig.ticket_tag_id is None:
            return await interaction.response.send_message("")
        channel: ForumChannel = await self.guilds[guild_id].fetch_channel(gconfig.ticket_forum_id)  # ty: ignore[invalid-assignment]
        thread = await channel.create_thread(name=f"Ticket from {interaction.user.display_name}", embed=message_embed(
            author=f"{interaction.user.display_name}", 
            author_av=interaction.user.display_avatar.url,
            title="New Ticket",
            description=text,
            footer="Respond using /tickets respond"
            ))
        
        tag = channel.get_tag(gconfig.ticket_tag_id)
        if tag is not None: await thread.thread.add_tags(tag)
        
        ticket = await Ticket.create(guild_id=guild_id, thread_id=thread.thread.id, user_id=interaction.user.id, anonymous=False)

        #TODO: stub
        await interaction.response.send_message(f"Ticket created with id {ticket.id}. (TODO: FOLLOWUP BUTTON!)")
        await interaction.response.send_message(embed=message_embed(title=f"Created ticket in {channel.guild.name}", author=f"{ticket.id}"))

class TicketFollowupModal(Modal):
    def __init__(self):
        pass

logger = logging.getLogger("discord.shakra.tickets")

class TicketSubmissionCog(Cog):
    def __init__(self, bot: Shakra) -> None:
        self.bot = bot
        self.logger = bot.logger.getChild("Tickets")
    
    @slash_cmd(name="ticket")
    @dm_only()
    async def create_ticket(self, interaction: Interaction):
        """Create a ticket in a server you're a member of.

        Args:
            interaction (Interaction): _description_
        """
        assert isinstance(interaction.user, User)
        guilds: list[Guild] = []
        for guildConfig in await GuildConfig.all():
            guild = self.bot.get_guild(guildConfig.guild_id)
            if guild is None:
                logger.warning(f"Bot not a member of guild {guildConfig.guild_id}, ignoring...")
                continue
            if guild.get_member(interaction.user.id) is not None:
                guilds.append(guild)
        if len(guilds) == 0:
            await interaction.response.send_message(f"You don't appear to be in any servers moderated by {APP_NAME}!")
            return
        
        
        await interaction.response.send_modal(SubmitTicketModal(guilds))
            
    

@guild_only
@default_permissions(moderate_members=True)
class TicketReceptionCog(GroupCog, group_name="tickets"):
    def __init__(self, bot: Shakra) -> None:
        self.bot = bot
        self.logger = bot.logger.getChild("Tickets")
    
    @slash_cmd(name="setup")
    @guild_only()
    async def setup(self, interaction: Interaction, channel: ForumChannel):
        """Set up a forum to receive tickets & appeals from users.
        
        Tickets will be given the tag [TICKET].
        Appeals will be given the tag [APPEAL].

        Args:
            channel (ForumChannel): The forum to direct tickets to.
        """
        config, _ = await GuildConfig.get_or_create(guild_id=interaction.guild_id)
        

        config.ticket_forum_id = channel.id
        needs_ticket_tag = True if config.ticket_tag_id is None else channel.get_tag(config.ticket_tag_id) is None
        needs_appeal_tag = True if config.appeal_tag_id is None else channel.get_tag(config.appeal_tag_id) is None
        
        #TODO: This fails on first setup, only one tag is created. The alternative is more painful than just running the command twice though so. Oh well!
        
        if needs_ticket_tag:
            tag = await channel.create_tag(name="Ticket", emoji=PartialEmoji.from_str("🎫"), reason=f"{APP_NAME} ticket setup by @{interaction.user.name}")
            config.ticket_tag_id = tag.id
        
        if needs_appeal_tag:
            tag = await channel.create_tag(name="Appeal", emoji=PartialEmoji.from_str("🎟️"), reason=f"{APP_NAME} ticket setup by @{interaction.user.name}")
            config.appeal_tag_id = tag.id
        
        
        await config.save()
        await interaction.response.send_message(f"Ticket setup successful to channel <#{config.ticket_forum_id}> & tags set up!")
    
    @slash_cmd(name="respond")
    async def respond(self, interaction: Interaction, content: str):
        if not isinstance(interaction.channel, Thread):
            return await interaction.response.send_message("May only be used in a ticket thread!", ephemeral=True)
        
        guild_config = await GuildConfig.get_or_none(guild_id=interaction.guild_id)
        if guild_config is None or interaction.channel.parent_id != guild_config.ticket_forum_id:
            return await interaction.response.send_message("May only be used in a ticket thread!", ephemeral=True)
        
        ticket = await Ticket.get_or_none(thread_id=interaction.channel.id)
        if ticket is None:
            await interaction.response.send_message("Could not find the ticket this thread is associated with! Locking this thread...")
            await interaction.channel.edit(locked=True)
            return
        
        user = self.bot.get_user(ticket.user_id)
        if user is None:
            return await interaction.response.send_message(f"Could not contact the user! Reach out to them to ensure they can still receive DMs from {APP_NAME}")

        await user.send(embed=message_embed(
            title="Ticket followup",
            description=content
        ))