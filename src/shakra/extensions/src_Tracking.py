import asyncio
import re
from datetime import timedelta
from itertools import batched

from discord import Interaction, Message, NotFound, RawReactionActionEvent, TextChannel
from discord.app_commands import command, default_permissions, guild_only
from discord.ext.commands import Cog, GroupCog
from discord.ext.tasks import loop
from discord.utils import escape_markdown, utcnow
from speedruncompy import GetModerationGames, GetModerationRuns, Verified
from speedruncompy.api import Forbidden, ServerException

from .. import Shakra
from ..models import SrcTrackingChannel
from ..utils import DEV_ID, GUILD_IDS, ConfirmationModal, get_src_game

TRACKING_RE = re.compile(
    r"\`(?P<category_name>.+)\` in (?P<run_time>.+) by [^\(\)]+(?P<obsolete>Obsolete)?\n<https:\/\/www.speedrun.com\/(?P<game_url>\w+)\/run\/(?P<run_id>[\w]+)>(?:\n\*\*Claimed by (?P<claimant_name>.+) <t:(?P<claim_time>\d+):R>\*\*)?"
)

CLAIM_EMOJI = "✅"
UNCLAIM_EMOJI = "❌"

async def setup(bot: Shakra):
    GUILDS = [g for g in (bot.get_guild(id) for id in GUILD_IDS) if g is not None]
    
    await bot.add_cog(SrcTrackingCog(bot), guilds=GUILDS)

@guild_only
@default_permissions(manage_channels=True)
class SrcTrackingCog(GroupCog, group_name="src_tracking"):
    bot: Shakra
    
    def __init__(self, bot: Shakra) -> None:
        self.bot = bot
        self.logger = bot.logger.getChild("SrcTracking")

    async def cog_load(self):
        self.update_tracked_games.start()

    async def cog_unload(self):
        self.update_tracked_games.cancel()

    @command()
    async def add(self, interaction: Interaction, channel: TextChannel, game_name: str):
        """Add a game to be tracked in a given channel. Multiple games may be tracked in one channel; there is a limit of 1000 messages.

        Args:
            channel (TextChannel): Channel to post run messages to
            game_name (str): Name of the game on Speedrun.com
        """
        game = await get_src_game(game_name)
        if game is None:
            return await interaction.response.send_message(f"No game with name `{game}` found!")

        moderation_games = await GetModerationGames().perform()
        if not isinstance(moderation_games.games, list):
            return await interaction.response.send_message(
                f"Could not find moderated games; contact <@{DEV_ID}> to fix."
            )

        if not game.id in (g.id for g in moderation_games.games):
            return await interaction.response.send_message()

        async def add_tracking_channel(interaction: Interaction):
            await SrcTrackingChannel.create(
                guild_id=interaction.guild_id, channel_id=channel.id, game_id=game.id
            )
            await interaction.response.send_message(
                f"Added `{game.name}` to <#{channel.id}>.", ephemeral=True
            )

        await interaction.response.send_modal(
            ConfirmationModal(
                add_tracking_channel,
                "SRC Tracking Channel",
                f"Post pending runs for `{game.name}` to <#{channel.id}>?",
            )
        )

    @command()
    async def remove(self, interaction: Interaction, channel: TextChannel, game_name: str):
        """Remove a game from tracking. Note this will _not_ purge tracking messages!

        Args:
            channel (TextChannel): _description_
            game_name (str): _description_

        Returns:
            _type_: _description_
        """
        game = await get_src_game(game_name)
        if game is None:
            return await interaction.response.send_message(
                f"No game with name `{game_name}` found!", ephemeral=True
            )

        tracking = await SrcTrackingChannel.get_or_none(
            guild_id=interaction.guild_id, channel_id=channel.id, game_id=game.id
        )
        if tracking is None:
            return await interaction.response.send_message(
                f"No game tracking found for `{game.name}` in <#<{channel.id}>.", ephemeral=True
            )
        else:
            await tracking.delete()
            await interaction.response.send_message(
                f"Removed tracking for `{game.name} in <#{channel.id}>", ephemeral=True
            )

    @command()
    async def list(self, interaction: Interaction):
        """List all tracked games."""
        tracking = await SrcTrackingChannel.filter(guild_id=interaction.guild_id)
        if len(tracking) == 0:
            return await interaction.response.send_message(
                "No games are being tracked in this server!", ephemeral=True
            )
        await interaction.response.send_message(
            "\n".join([f"({t.game_id}): <#{t.channel_id}>" for t in tracking]), ephemeral=True
        )
        
    @Cog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        if payload.guild_id is None: return
        if payload.message_author_id != self.bot.own_id: return
        if payload.user_id == self.bot.own_id: return
        
        emoji_str = str(payload.emoji)
        if emoji_str != CLAIM_EMOJI and emoji_str != UNCLAIM_EMOJI: 
            return
        
        tracks = await SrcTrackingChannel.filter(guild_id=payload.guild_id, channel_id=payload.channel_id)
        if len(tracks) == 0: return
        
        channel: TextChannel | None = self.bot.get_channel(payload.channel_id)  # ty: ignore[invalid-assignment]
        if channel is None: return
        
        try:
            message = await channel.fetch_message(payload.message_id)
        except NotFound:
            return
        
        match = TRACKING_RE.match(message.content)
        if match is None:
            return
        
        claimant = match.group("claimant_name")
        user = payload.member
        if user is None: return
        if emoji_str == CLAIM_EMOJI and claimant is None:
            await message.edit(content=f"{message.content}\n**Claimed by {escape_markdown(user.name)} <t:{int(utcnow().timestamp())}:R>**")
            await message.add_reaction(UNCLAIM_EMOJI)
            await message.clear_reaction(CLAIM_EMOJI)
        elif emoji_str == UNCLAIM_EMOJI and claimant == escape_markdown(user.name):
            await message.edit(content="\n".join(message.content.splitlines()[:2]))
            await message.add_reaction(CLAIM_EMOJI)
            await message.clear_reaction(UNCLAIM_EMOJI)

    @loop(minutes=1)
    async def update_tracked_games(self):
        try:
            for track in await SrcTrackingChannel.all():
                guild = self.bot.get_guild(track.guild_id)
                if guild is None:
                    self.logger.error(
                        f"No longer member of guild {track.guild_id}, removing from tracking..."
                    )
                    await track.delete()
                    continue
                channel: TextChannel | None = self.bot.get_channel(track.channel_id)  # ty: ignore[invalid-assignment]
                if not isinstance(channel, TextChannel):
                    self.logger.error(
                        f"Can no longer find channel for {guild.name} tracking {track.game_id}, skipping..."
                    )
                    continue

                try:
                    moderation_runs = await GetModerationRuns(
                        track.game_id, limit=100, verified=Verified.PENDING
                    ).perform_all()
                except Forbidden:
                    self.logger.error(f"Cannot see tracked game {track.game_id}, removing relevant")
                    await track.delete()
                    await channel.send(
                        f"I can no longer see runs of this game ({track.game_id}); tracking has been halted. Please re-setup after adding HornetBot as a verifier."
                    )
                    continue

                game = moderation_runs._gameDict[track.game_id]

                logged_runs: set[str] = set()
                history = [m async for m in channel.history(limit=1000)]
                to_delete: set[Message] = set()
                for message in history:
                    if message.author.id != self.bot.own_id:
                        continue
                    match = TRACKING_RE.prefixmatch(message.content)
                    if match is None:
                        continue
                    game_url, run_id = (match.group("game_url"), match.group("run_id"))
                    assert game_url is not None and run_id is not None
                    if game_url != game.url:
                        continue
                    if (run_id not in moderation_runs._runDict) or (run_id in logged_runs):
                        # Run no longer in queue or in queue multiple times; remove it
                        to_delete.add(message)
                    else:
                        logged_runs.add(run_id)
                
                # Batch deletion enters into audit log, so under a threshold we'll delete them one-by-one.
                if len(to_delete) < 20:
                    await asyncio.gather(*[message.delete() for message in to_delete])
                else:
                    await asyncio.gather(*[channel.delete_messages(batch) for batch in batched(to_delete, 100)])

                message_sends = []
                
                for run in moderation_runs.runs:
                    if run.id in logged_runs:
                        continue

                    subcatname = ""
                    for value in (moderation_runs._valueDict[id] for id in run.valueIds):
                        variable = moderation_runs._variableDict[value.variableId]
                        if variable.isSubcategory and not variable.archived:
                            subcatname += f" - {value.name}"

                    category = moderation_runs._categoryDict[run.categoryId]

                    if category.isPerLevel and run.levelId is not None:
                        level = moderation_runs._levelDict[run.levelId]
                        category_str = level.name
                    else:
                        category_str = category.name

                    primary_t: float = run.time if (run.time is not None) else run.timeWithLoads  # ty: ignore[invalid-assignment]

                    player_names = escape_markdown(
                        " & ".join([moderation_runs._playerDict[pid].name for pid in run.playerIds])
                    )

                    runstring = f"`{game.name}: {category_str}{subcatname}` in {format_time(primary_t)} by {player_names}\n<https://www.speedrun.com/{game.url}/run/{run.id}>"

                    message_sends.append(channel.send(runstring))

                await asyncio.gather(*message_sends)
                
                # Ensure all messages have been reacted, and backreference identical submissions
                history = [m async for m in channel.history(limit=1000)]
                for message in history:
                    if message.author.id != self.bot.own_id:
                        continue
                    match = TRACKING_RE.prefixmatch(message.content)
                    if match is None:
                        continue
                    claimant = match.group("claimant_name")
                    reactions = {str(r.emoji): r for r in message.reactions}
                    if not isinstance(claimant, str):
                        if reactions.get(CLAIM_EMOJI) is None:
                            await message.add_reaction(CLAIM_EMOJI)
                    else:
                        if reactions.get(UNCLAIM_EMOJI) is None:
                            await message.add_reaction(UNCLAIM_EMOJI)
                            
        except (ServerException) as e:
            self.logger.info(f"update_tracked_games: error from Speedrun.com ({e.__class__.__name__}), skipping iteration...")
        except Exception as e:
            self.logger.error("update_tracked_games: unknown error: ", exc_info=e)


def format_time(t: float) -> str:
    # TODO: this feels stupid, think of a better way to do this
    td = str(timedelta(seconds=t))
    if "." in td:
        td = td[:td.index(".") + 3]  # Strip microseconds if present bc timedelta shows micro- rather than milli-
    while td.startswith(("0", ":")):
        td = td[1:]
    return td


async def send_reacted_message(channel: TextChannel, content: str):
    message = await channel.send(content)
    await message.add_reaction(CLAIM_EMOJI)