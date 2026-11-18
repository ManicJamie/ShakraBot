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

from ...utils import GUILD_IDS, message_embed

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


async def setup(bot: Shakra):
    GUILDS = [g for g in (bot.get_guild(id) for id in GUILD_IDS) if g is not None]

    await bot.add_cog(ModerationCog(), guilds=GUILDS)

    bot.tree.add_command(ctxmnu_ban, guilds=GUILDS)
    bot.tree.add_command(ctxmnu_warn, guilds=GUILDS)
    bot.tree.add_command(ctxmnu_relay, guilds=GUILDS)


# TODO: Is asserting interaction and member guild are the same necessary?


class ModerationCog(Cog):
    async def cog_load(self) -> None: ...

    @slash_cmd(name="ban")
    @guild_only
    @default_permissions(ban_members=True)
    async def ban(self, interaction: Interaction, member: Member, reason: str | None):
        """Bans a user, DMing them a ban reason & prompt to appeal if available.

        Args:
            member (Member): The member to ban
        """
        await interaction.response.send_modal(BanModal(member))

    @slash_cmd(name="warn")
    @guild_only
    @default_permissions(moderate_members=True)
    async def warn(self, interaction: Interaction, member: Member, content: str | None):
        """DM a warning to a user.

        Args:
            member (Member): The member to warn
        """
        await interaction.response.send_modal(WarnModal(member))

    @slash_cmd(name="relay", description="Relay a message to a channel")
    @guild_only
    @default_permissions(manage_messages=True)
    async def relay(
        self,
        interaction: Interaction,
        channel: Thread | TextChannel | None,
        content: str | None,
    ):
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


async def do_relay(channel: Messageable, content: str):
    return await channel.send(content=content)


@context_menu(name="Ban User")
@guild_only
@default_permissions(ban_members=True)
async def ctxmnu_ban(interaction: Interaction, member: Member):
    await interaction.response.send_modal(BanModal(member))


@context_menu(name="Warn User")
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
        self, member: Member, *, timeout: float | None = None, custom_id: str = MISSING
    ) -> None:
        super().__init__(
            title=f"Warn user @{member.name}", timeout=timeout, custom_id=custom_id
        )
        self.member = member

        self.reason_input = TextInput(
            placeholder="Reason is DMed to the user.", style=TextStyle.long
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
        self, member: Member, *, timeout: float | None = None, custom_id: str = MISSING
    ) -> None:
        super().__init__(
            title=f"Ban @{member.name}", timeout=timeout, custom_id=custom_id
        )
        self.member = member

        self.reason_input = TextInput(
            placeholder="Reason is DMed to the user.", style=TextStyle.long
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
