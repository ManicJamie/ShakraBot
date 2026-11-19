import logging
import re
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any, Unpack

from discord import (
    ButtonStyle,
    Colour,
    Embed,
    File,
    Interaction,
    Permissions,
)
from discord.app_commands import MissingPermissions, Transformer, check
from discord.ext.commands import BadArgument, Context, Converter
from discord.ui import (
    ActionRow,
    Button,
    Container,
    Item,
    LayoutView,
    Modal,
    TextDisplay,
)
from pytimeparse.timeparse import timeparse
from speedruncompy import Game, GetSearch

if TYPE_CHECKING:
    from discord.permissions import _PermissionsKwargs
    

GUILD_IDS = [1113528044347469984]

APP_NAME = "Shakra"
"""Name as displayed by the application in messages"""
APP_ID = "shakra"
"""Name as displayed in logs"""
APP_COLOUR = Colour.from_rgb(200, 20, 20)

DEV_ID = 196347053100630016
"""User ID used to add a person to DM on uncaught errors."""

logger = logging.getLogger(f"discord.{APP_ID}")

@check
async def is_bot_owner(intercontext: Interaction | Context) -> bool:
    if isinstance(intercontext, Interaction): 
        return intercontext.user.id == 196347053100630016
    return intercontext.author.id == 196347053100630016

def duration_convert(duration: str) -> float:
    if duration.isnumeric(): duration += "s"  # For unformatted times, we expect seconds by default
    length = timeparse(duration)
    if length is None:
        raise BadArgument("Could not parse duration! Enter in format `60s` or `5m10s`.")
    return float(length)

class DurationTransformer(Transformer):
    async def transform(self, interaction: Interaction, duration: str) -> float:
        return duration_convert(duration)

class DurationConverter(Converter):
    async def convert(self, ctx: Context, argument: str) -> float:
        return duration_convert(argument)

def message_embed(title         : str | None = None, 
                  description   : str | None = None,
                  url           : str | None = None,
                  timestamp     : datetime | None = None,
                  thumbnail     : str | File |  None = None,
                  image         : str | File | None = None,
                  author        : str | None = None,
                  author_url    : str | None = None,
                  author_av     : str | File | None = None,
                  fields        : list[tuple[str, str, bool]] | None = None,
                  footer        : str | None = None,
                  footer_av : str | File | None = None,
                  colour: Colour = APP_COLOUR):
    embed = Embed(colour=colour, title=title, description=description, url=url, timestamp=timestamp)
    
    # File to uris - user is responsible for attaching the file to the message!
    if isinstance(thumbnail, File): thumbnail = thumbnail.uri
    if isinstance(image, File): image = image.uri
    if isinstance(author_av, File): author_av = author_av.uri
    if isinstance(footer_av, File): footer_av = footer_av.uri
    
    if author is not None:
        embed.set_author(name=author, url=author_url, icon_url=author_av)
    if fields is not None:
        for field_name, field_value, inline in fields:
            embed.add_field(name=field_name, value=field_value, inline=inline)
    if footer is not None:
        embed.set_footer(text=footer, icon_url=footer_av)
    if thumbnail is not None:
        embed.set_thumbnail(url=thumbnail)
    if image is not None:
        embed.set_image(url=image)
    
    return embed

def has_permissions_or_private(**perms: Unpack[_PermissionsKwargs]) -> Callable:
    """Polyfill to allow commands to be used in private contexts as if user is admin."""
    invalid = perms.keys() - Permissions.VALID_FLAGS.keys()
    if invalid:
        raise TypeError(f'Invalid permission(s): {", ".join(invalid)}')

    def predicate(interaction: Interaction) -> bool:
        if not interaction.context.guild: return True
        permissions = interaction.permissions

        missing = [perm for perm, value in perms.items() if getattr(permissions, perm) != value]

        if not missing:
            return True

        raise MissingPermissions(missing)

    return check(predicate)

EMOJI_RE = re.compile(r"<:(\w*):(\d*)>")

def to_true_emoji(refstring: str):
    EMOJI_RE.match(refstring)

class ConfirmationView(LayoutView):
    def __init__(self, callback: Callable[[Interaction], Awaitable[Any]], title: str, description: str, extras: list[Item] | None = None, *, timeout: float | None = None) -> None:
        if extras is None:
            extras = []
        super().__init__(timeout=timeout)
        
        class SubmitButton(Button):
            async def callback(self, interaction: Interaction) -> Any:
                await callback(interaction)
        
        class CancelButton(Button):
            async def callback(self, interaction: Interaction) -> Any:
                await interaction.delete_original_response()
        
        self.submit_button = SubmitButton(label="Yes", style=ButtonStyle.primary)
        self.cancel_button = CancelButton(label="No", style=ButtonStyle.secondary)
        
        self.add_item(Container(*[
            TextDisplay(f"# {title}\n{description}"),
            *extras
        ], accent_colour=APP_COLOUR)).add_item(
            ActionRow(self.submit_button, self.cancel_button)
        )

class ConfirmationModal(Modal):
    def __init__(self, callback: Callable[[Interaction], Awaitable[Any]], title: str, description: str, extras: list[Item] | None = None, *, timeout: float | None = None) -> None:
        if extras is None:
            extras = []
        super().__init__(timeout=timeout, title=title)
        
        self.callback = callback
        
        
        self.add_item(TextDisplay(description))
        for e in extras: self.add_item(e)
    
    async def on_submit(self, interaction: Interaction):
        await self.callback(interaction)

def get_parent_id(interaction: Interaction) -> tuple[int, bool]:
    """Retrieve the parent id & boolean isGuild"""
    if interaction.context.guild:
        return (interaction.guild_id, True)  # ty: ignore[invalid-return-type]
    return (interaction.user.id, False)

async def get_src_game(name: str) -> Game | None:
    gameSearch = await GetSearch(name, favorExactMatches=True, includeGames=True).perform()
    if len(gameSearch.gameList) == 0:
        return None
    return gameSearch.gameList[0]


# TODO: Polyfills for app command transforms?

# class PartialMessageTransformer(Transformer):
#     async def transform(self, interaction: Interaction, value: str) -> PartialMessage:
#         return await super().transform(interaction, value)

# class MessageTransformer(Transformer):
#     async def transform(self, interaction: Interaction, value: str) -> Message:
#         ...
