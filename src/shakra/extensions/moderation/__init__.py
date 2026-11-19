from typing import TYPE_CHECKING

from discord import (
    ChannelType,
    Interaction,
    Member,
    Message,
    TextChannel,
    TextStyle,
    Thread,
)
from discord.abc import Messageable
from discord.app_commands import command as slash_cmd
from discord.app_commands import (
    context_menu,
    default_permissions,
    guild_only,
)
from discord.ext.commands import Cog
from discord.ui import (
    ChannelSelect,
    Label,
    Modal,
    TextInput,
)
from discord.utils import MISSING

from ...utils import APP_NAME, ConfirmationModal, message_embed
from .appeal import AppealsCog

if TYPE_CHECKING:
    from ... import Shakra

TEXT_CHANNEL_TYPES = [
    ChannelType.text,
    ChannelType.private,
    ChannelType.voice,
    ChannelType.group,
    ChannelType.news,
    ChannelType.news_thread,
    ChannelType.public_thread,
    ChannelType.private_thread,
]

BOT: Shakra


async def setup(bot: Shakra):
    global BOT  # TODO: undo this hack
    BOT = bot

    await bot.add_cog(ModerationCog(bot))
    await bot.add_cog(AppealsCog(bot))
    # await bot.add_cog(ModerationMuteCog())  # Mutes left out due to lack of need for them. Left unfinished.

    @context_menu(name="Edit Relayed Message")
    @guild_only
    @default_permissions(manage_messages=True)
    async def ctxmnu_relay_edit(interaction: Interaction, message: Message):
        """Edit an existing relayed message."""
        if message.author.id != bot.own_id:
            return await interaction.response.send_message(
                f"Cannot edit a message {APP_NAME} did not send!", ephemeral=True
            )
        else:
            await interaction.response.send_modal(EditRelayModel(message))

    bot.tree.add_command(ctxmnu_ban)
    bot.tree.add_command(ctxmnu_warn)
    bot.tree.add_command(ctxmnu_relay)
    bot.tree.add_command(ctxmnu_relay_edit)
    bot.tree.add_command(ctxmnu_softban)


# TODO: Is asserting interaction and member guild are the same necessary?


class ModerationCog(Cog):
    def __init__(self, bot: Shakra) -> None:
        self.bot = bot
        super().__init__()

    @slash_cmd(name="ban")
    @guild_only
    @default_permissions(ban_members=True)
    async def ban(self, interaction: Interaction, member: Member, reason: str | None):
        """Bans a user, DMing them a ban reason & prompt to appeal if available.

        Args:
            member (Member): The member to ban
        """
        await interaction.response.send_modal(BanModal(member, reason))

    @slash_cmd(name="warn")
    @guild_only
    @default_permissions(moderate_members=True)
    async def warn(self, interaction: Interaction, member: Member, content: str | None):
        """DM a warning to a user.

        Args:
            member (Member): The member to warn
        """
        await interaction.response.send_modal(WarnModal(member, content))

    @slash_cmd(name="relay")
    @guild_only
    @default_permissions(manage_messages=True)
    async def relay(
        self,
        interaction: Interaction,
        channel: Thread | TextChannel | None,
        content: str | None,
    ):
        """Relay a message as if sent by the bot.

        Args:
            channel: The channel to send the message to.
            content: The content of the message (max 2000 characters)
        """
        if content is None or channel is None:
            return await interaction.response.send_modal(
                RelayModal(content or "", channel=channel)
            )
        if len(content) > 2000:
            return await interaction.response.send_message(
                "Can't relay message longer than 2000 characters!", ephemeral=True
            )
        await interaction.response.defer(ephemeral=True)
        msg = await do_relay(channel, content)
        await interaction.followup.send(content=f"Relayed message: {msg.jump_url}")

    @slash_cmd(name="softban")
    @guild_only
    @default_permissions(ban_members=True)
    async def softban(self, interaction: Interaction, member: Member):
        """Softban a user (kick & delete past day of messages).

        Args:
            member (Member): The member to softban.
        """
        await do_softban(member)
        await self.bot.logged_response(interaction, f"Softbanned <@{member.id}>")


async def do_warning(member: Member, reason: str):
    await member.send(
        embed=message_embed(title=f"Warning in {member.guild.name}", description=reason)
    )


async def do_ban(member: Member, reason: str):
    await member.send(
        embed=message_embed(
            title=f"You have been banned from {member.guild.name}",
            description=reason,
            footer="If you believe this is in error, type /appeal below.",
        )
    )
    await member.ban(reason=reason)

@context_menu(name="Softban")
@guild_only
@default_permissions(ban_members=True)
async def ctxmnu_softban(interaction: Interaction, member: Member):
    async def on_submit(i: Interaction):
        await do_softban(member)
        await BOT.logged_response(i, f"Softbanned user <@{member.id}>")

    await interaction.response.send_modal(
        ConfirmationModal(
            callback=on_submit,
            title=f"Softban user @{member.name}",
            description=f"Softban <@{member.id}>? This will delete the past day of messages. No notification will be sent.",
        )
    )


async def do_softban(member: Member):
    await member.ban(delete_message_days=1, reason="Softban")
    await member.unban(reason="Softban")


async def do_relay(channel: Messageable, content: str):
    await channel.send(content=content)


async def do_relay_edit(message: Message, content: str):
    await message.edit(content=content)


@context_menu(name="Ban")
@guild_only
@default_permissions(ban_members=True)
async def ctxmnu_ban(interaction: Interaction, member: Member):
    await interaction.response.send_modal(BanModal(member))

@context_menu(name="Warn")
@guild_only
@default_permissions(ban_members=True)
async def ctxmnu_warn(interaction: Interaction, member: Member):
    await interaction.response.send_modal(WarnModal(member))


@context_menu(name="Relay Message")
@guild_only
@default_permissions(manage_messages=True)
async def ctxmnu_relay(interaction: Interaction, message: Message):
    if len(message.content) > 2000:
        return await interaction.response.send_message(
            "Can't relay message longer than 2000 characters!", ephemeral=True
        )
    await interaction.response.send_modal(RelayModal(message.content))


class WarnModal(Modal):
    def __init__(
        self,
        member: Member,
        content: str | None = None,
        *,
        timeout: float | None = None,
        custom_id: str = MISSING,
    ) -> None:
        super().__init__(
            title=f"Warn user @{member.name}", timeout=timeout, custom_id=custom_id
        )
        self.member = member

        self.reason_input = TextInput(
            placeholder="Reason is DMed to the user.", style=TextStyle.long, default=content
        )
        self.add_item(Label(text="Warning text", component=self.reason_input))

    async def on_submit(self, interaction: Interaction):
        reason: str = self.reason_input.value
        await do_warning(member=self.member, reason=reason)
        await interaction.response.send_message(
            ephemeral=False,
            embed=message_embed(
                title="Warned",
                description=reason,
                fields=[("User", f"<@{self.member.id}>", True)],
            ),
        )


class BanModal(Modal):
    def __init__(
        self,
        member: Member,
        content: str | None = None,
        *,
        timeout: float | None = None,
        custom_id: str = MISSING,
    ) -> None:
        super().__init__(
            title=f"Ban @{member.name}", timeout=timeout, custom_id=custom_id
        )
        self.member = member

        self.reason_input = TextInput(
            placeholder="Reason is DMed to the user.", style=TextStyle.long, default=content
        )
        self.add_item(Label(text="Ban Reason", component=self.reason_input))

    async def on_submit(self, interaction: Interaction) -> None:
        reason: str = self.reason_input.value
        await do_ban(self.member, reason)
        await interaction.response.send_message(
            embed=message_embed(
                title="Banned",
                description=reason,
                fields=[("User", f"<@{self.member.id}>", True)],
            )
        )

    async def on_error(self, interaction: Interaction, error: Exception) -> None:
        return await super().on_error(interaction, error)


class RelayModal(Modal, title="Relay message"):
    def __init__(
        self,
        content: str,
        *,
        channel: Thread | TextChannel | None = None,
        title: str = MISSING,
        timeout: float | None = None,
        custom_id: str = MISSING,
    ) -> None:
        super().__init__(title=title, timeout=timeout, custom_id=custom_id)

        self.relay_input = TextInput(
            placeholder="Message to be relayed",
            style=TextStyle.long,
            min_length=1,
            max_length=2000,
            required=True,
            default=content,
        )
        self.add_item(Label(text="Relayed message", component=self.relay_input))

        self.channel_selector = ChannelSelect(
            channel_types=TEXT_CHANNEL_TYPES,
            required=True,
            default_values=[channel] if channel is not None else [],
        )

        self.add_item(
            Label(text="Channel to relay to", component=self.channel_selector)
        )

    async def on_submit(self, interaction: Interaction) -> None:
        # TYPING: selector type restriction won't allow selecting non-messageable channels
        channel: Thread | TextChannel = await self.channel_selector.values[0].fetch()  # ty: ignore[invalid-assignment]

        await do_relay(channel=channel, content=self.relay_input.value)
        await interaction.response.send_message(
            content=f"Relayed to <#{channel.id}>", ephemeral=True
        )

    async def on_error(self, interaction: Interaction, error: Exception) -> None:
        return await super().on_error(interaction, error)

class EditRelayModel(Modal, title="Edit relayed message"):
    def __init__(
        self,
        message: Message,
        *,
        timeout: float | None = None,
        custom_id: str = MISSING,
    ) -> None:
        super().__init__(title="Editing relayed message", timeout=timeout, custom_id=custom_id)
        self.message = message

        self.relay_input = TextInput(
            placeholder="Message to be relayed",
            style=TextStyle.long,
            min_length=1,
            max_length=2000,
            required=True,
            default=message.content,
        )
        self.add_item(Label(text="Relayed message", component=self.relay_input))

    async def on_submit(self, interaction: Interaction) -> None:
        # TYPING: selector type restriction won't allow selecting non-messageable channels
        await do_relay_edit(self.message, self.relay_input.value)
        await interaction.response.send_message("Edited message!", ephemeral=True)

    async def on_error(self, interaction: Interaction, error: Exception) -> None:
        return await super().on_error(interaction, error)
