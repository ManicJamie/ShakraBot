import asyncio
import logging
import time
from typing import TYPE_CHECKING

from discord import Interaction, Message, PartialEmoji, RawReactionActionEvent
from discord.app_commands import (
    allowed_contexts,
    allowed_installs,
    command,
    default_permissions,
    describe,
)
from discord.ext.commands import Cog, Context, GroupCog, cooldown, hybrid_command
from discord.ui import Modal

from ..models import Ready
from ..utils import GUILD_IDS, DurationConverter

if TYPE_CHECKING:
    from .. import Shakra


READY_EMOJI = "🇷"
READY_COUNTDOWN = 15

logger = logging.getLogger("discord.shakra.race_utils")


async def setup(bot: Shakra):
    GUILDS = [g for g in (bot.get_guild(id) for id in GUILD_IDS) if g is not None]

    await bot.add_cog(RaceUtilsGlobal(bot))
    await bot.add_cog(RaceUtilsCog(bot), guilds=GUILDS)


async def countdown_timeout(msg: Message, exit_time: int):
    await asyncio.sleep(exit_time - time.time())
    await msg.edit(content=f"{msg.content} Go!")


class RaceUtilsCog(Cog):
    bot: Shakra

    def __init__(self, bot: Shakra) -> None:
        self.bot = bot

    @Cog.listener("on_raw_reaction_add")
    async def ready_handler(self, payload: RawReactionActionEvent):
        if payload.emoji != PartialEmoji.from_str(READY_EMOJI):
            return  # TODO: per-guild config here

        if (ready := await Ready.get_or_none(id=payload.message_id)) is None:
            return

        if (channel := await self.bot.get_messageable_safe(payload.channel_id)) is None:
            return
        ready_msg = await channel.fetch_message(payload.message_id)

        for reaction in filter(lambda x: READY_EMOJI == str(x.emoji), ready_msg.reactions):
            if reaction.count > ready.ready_count:
                exit_time = int(time.time() + 15)
                msg = await ready_msg.reply(f"<t:{exit_time}:R>")
                await countdown_timeout(msg, exit_time)
                await ready.delete()

    @hybrid_command(
        name="ready",
        description="Start a countdown after the specified number of reacts are received.",
        aliases=["r"],
    )
    @describe(count="Number of reactions needed to start the countdown")
    @allowed_installs(guilds=True, users=True)
    @allowed_contexts(guilds=True, dms=True)
    @cooldown(1, 10)
    async def ready(self, ctx: Context, count: int):
        msg = await ctx.reply(READY_EMOJI, mention_author=False)
        await Ready.create(id=msg.id, ready_count=count)
        await msg.add_reaction(READY_EMOJI)


class RaceUtilsGlobal(Cog):
    @hybrid_command(
        name="countdown", description="Starts a `duration` second countdown.", aliases=["c"]
    )
    @allowed_installs(guilds=True, users=True)
    @allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def countdown(self, ctx: Context, duration: DurationConverter):
        assert isinstance(duration, float)  # TYPING: converter annotations are stupid :)

        await ctx.defer()
        exit_time = int(time.time() + duration)
        msg: Message = await ctx.send(f"<t:{exit_time}:R>")
        await countdown_timeout(msg, exit_time)


@default_permissions(manage_channels=True)
class ManageRaceUtilsCog(GroupCog, name="manage_racing"):
    bot: Shakra

    def __init__(self, bot: Shakra) -> None:
        self.bot = bot

    @command(name="group_set")
    async def manage_racing_group(self, interaction: Interaction, name: str):
        """Create or edit a group of racing VCs & text channels.

        Args:
            name (str): Name for this group of VCs.
        """
        # TODO Stub


class RaceVCGroupsModal(Modal): ...
