from itertools import batched
from typing import TYPE_CHECKING

import orjson
from discord import ButtonStyle, Emoji, Interaction, PartialEmoji, TextStyle
from discord.app_commands import (
    Choice,
    Group,
    allowed_contexts,
    autocomplete,
    default_permissions,
)
from discord.app_commands import command as slash_cmd
from discord.ext.commands import Cog, CommandError, CommandNotFound, Context
from discord.ui import (
    ActionRow,
    Button,
    Container,
    Label,
    LayoutView,
    Modal,
    TextDisplay,
    TextInput,
    View,
)
from discord.utils import MISSING
from orjson import JSONDecodeError

from ..models import Tag, TagContext, TagLabelStyle
from ..utils import APP_COLOUR, is_bot_owner, message_embed
from ..utils import logger as logger_parent

if TYPE_CHECKING:
    from .. import Shakra

cog: TagCog

async def setup(bot: Shakra):
    global cog
    
    cog = TagCog(bot)
    await bot.add_cog(cog)
    bot.tree.add_command(cog.ManageTagsGroup())
    bot.cmd_failure_handlers.append(cog.txt_cmd_fallback)

async def teardown(bot: Shakra):
    bot.cmd_failure_handlers.remove(cog.txt_cmd_fallback)


# TODO: cmd permission


async def retrieve_tag(interaction: Interaction, name: str):
    if interaction.context.guild:
        return await Tag.get_or_none(
            parent_id=interaction.guild_id, context=TagContext.GUILD, name=name
        )
    else:
        return await Tag.get_or_none(
            parent_id=interaction.user.id, context=TagContext.USER, name=name
        )


async def create_tag(interaction: Interaction, name: str, content: str, tag: Tag | None = None):
    if isinstance(tag, Tag):
        tag = tag.update_from_dict({"name": name, "content": content})
        await tag.save()
        return tag

    if interaction.context.guild:
        return await Tag.create(
            parent_id=interaction.guild_id, context=TagContext.GUILD, name=name, content=content
        )
    else:
        return await Tag.create(
            parent_id=interaction.user.id, context=TagContext.USER, name=name, content=content
        )


@allowed_contexts(guilds=True)
@default_permissions(send_messages=True)
class TagCog(Cog):
    bot: Shakra
    logger = logger_parent.getChild("tags")

    def __init__(self, bot: Shakra) -> None:
        self.bot = bot

    async def txt_cmd_fallback(self, context: Context, error: CommandError) -> bool:
        if isinstance(error, CommandNotFound) and context.guild is not None:
            failed_cmd = str(context.invoked_with)
            tag = await Tag.get_or_none(parent_id=context.guild.id, name=failed_cmd)
            if tag is None:
                raise error
            await self.reply_tag(context, tag)
            return True
        return False

    async def reply_tag(self, ctx: Context, tag: Tag):
        # replies do not need to label the tag, as the message is clearly visible to the user
        await ctx.reply(tag.content, mention_author=False)

    async def send_tag(
        self, interaction: Interaction, tag: Tag, style: TagLabelStyle, private: bool = False
    ):
        view = MISSING

        match style:
            case TagLabelStyle.NONE:
                content = tag.content
            case TagLabelStyle.PREFIX:
                content = f"-# {tag.name}\n{tag.content}"
            case TagLabelStyle.BUTTON:
                content = tag.content
                view = View(timeout=None).add_item(
                    Button(label=tag.name, disabled=True, style=ButtonStyle.primary)
                )
            case _:
                self.logger.error(
                    f"send_tag called with unknown style {style}, falling back to NONE"
                )
                content = tag.content

        await interaction.response.send_message(content=content, view=view, ephemeral=private)

    async def tag_search_callback(self, interaction: Interaction, name: str) -> list[Choice[str]]:
        if interaction.context.guild:
            searchfilter = Tag.filter(
                parent_id=interaction.guild_id, context=TagContext.GUILD, name__icontains=name
            )
        else:
            searchfilter = Tag.filter(
                parent_id=interaction.user.id, context=TagContext.USER, name__icontains=name
            )
        return [
            Choice(name=choice.name, value=choice.name)
            for choice in await searchfilter.order_by("name")
        ][:25]

    @default_permissions(manage_channels=True)
    class ManageTagsGroup(Group, name="manage_tags"):
        @slash_cmd()
        async def set(self, interaction: Interaction, name: str, content: str | None):
            """Create or update a tag.

            Args:
                name (str): The name of the tag to set
                content (str | None): The new content of the tag
            """
            maybe_tag = await retrieve_tag(interaction, name)
            if content is None:
                await interaction.response.send_modal(TagSetModal(maybe_tag, tag_name=name))
            else:
                tag = await create_tag(interaction, name, content, maybe_tag)
                await interaction.response.send_message(
                    embed=message_embed(f"Tag `{tag.name}` created!", description=tag.content),
                    ephemeral=True,
                )

        @slash_cmd()
        async def delete(self, interaction: Interaction, name: str):
            """Delete a tag.

            Args:
                name (str): The name of the tag to delete
            """
            tag = await retrieve_tag(interaction, name)
            if tag is None:
                await interaction.response.send_message(
                    f"Couldn't find tag `{name}`!", ephemeral=True
                )
                return
            await tag.delete()
            await interaction.response.send_message(
                embed=message_embed(f"Tag `{name}` delted!", description=tag.content)
            )

    @slash_cmd(name="tag")
    @autocomplete(name=tag_search_callback)
    async def get(self, interaction: Interaction, name: str, private: bool = False):
        """Get a tag defined in this server.

        Args:
            name (str): The name of the tag to fetch
            private (bool, optional): Set to true to show the tag only to yourself.
        """

        tag = await retrieve_tag(interaction, name)
        if tag is None:
            await interaction.response.send_message(f"Couldn't find tag `{name}`!", ephemeral=True)
            return
        await self.send_tag(interaction, tag, TagLabelStyle.NONE, private=private)  # TODO: configurable style
    
    @slash_cmd(name="tag_list")
    async def tag_list(self, interaction: Interaction):
        """Get an interactive list of all available tags."""
        if interaction.context.guild:
            tags = await Tag.filter(parent_id=interaction.guild_id, context=TagContext.GUILD)
        else:
            tags = await Tag.filter(parent_id=interaction.user.id, context=TagContext.USER)
        if len(tags) == 0:
            await interaction.response.send_message("No tags to list!", ephemeral=True)
            return
        await interaction.response.send_message(view=TagListView(tags, interaction), ephemeral=True)
    
    @slash_cmd(name="import_tags")
    @default_permissions(manage_channels=True)
    @is_bot_owner
    async def import_tags(self, interaction: Interaction):
        """Bot admin-only tool to import tags in a local .json file to the bot."""
        if not interaction.context.guild:
            return await interaction.response.send_message("Must be in a guild!")
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            with open("./tags_import.json") as f:  # noqa: ASYNC230 # TODO: replace with non-blocking file IO
                tags: dict[str, str] = orjson.loads(f.read())
        except FileNotFoundError:
            return await interaction.followup.send("No file found!", ephemeral=True)
        except JSONDecodeError:
            return await interaction.followup.send("Import file contains invalid JSON!", ephemeral=True)
        
        created = []
        for name, content in tags.items():
            created.append(await create_tag(interaction, name, content, tag=await retrieve_tag(interaction, name)))
        
        await interaction.followup.send(f"Imported {len(created)} tags!", ephemeral=True)


class TagListActionRow(ActionRow):
    class PageScrollButton(Button):
        def __init__(self, increment: int, emoji: str | Emoji | PartialEmoji):
            super().__init__(emoji=emoji, style=ButtonStyle.secondary, label=None, disabled=False, custom_id=None, url=None)
            self.increment = increment
        
        async def callback(self, interaction: Interaction):
            assert isinstance(self.parent, TagListActionRow)
            await self.parent.list_view.change_page(self.increment)
            await interaction.response.edit_message(view=self.parent.list_view)
    
    def __init__(self, view: TagListView, id: int | None = None) -> None:
        super().__init__(*[], id=id)
        
        self.list_view = view
        
        self.back_button =self.PageScrollButton(-1, "◀️")
        self.forward_button = self.PageScrollButton(1, "▶️")
        
        self.add_item(self.back_button)
        self.add_item(self.forward_button)

        self.back_button.disabled = self.list_view.curr_page == 0
        self.forward_button.disabled = self.list_view.curr_page >= len(self.list_view.tags) - 1

class TagListView(LayoutView):
    tags: list[list[Tag]]  # Pages of rows of tags
    PAGE_SIZE = 25
    curr_page: int
    
    class TagListEntry(Button):
        tag: Tag
        
        def __init__(self, tag: Tag, *, style: ButtonStyle = ButtonStyle.secondary, disabled: bool = False, custom_id: str | None = None, url: str | None = None, emoji: str | Emoji | PartialEmoji | None = None, row: int | None = None, sku_id: int | None = None, id: int | None = None):
            super().__init__(style=style, label=tag.name, disabled=disabled, custom_id=custom_id, url=url, emoji=emoji, row=row, sku_id=sku_id, id=id)
            self.tag = tag
        
        async def callback(self, interaction: Interaction):
            await interaction.response.send_message(self.tag.content, ephemeral=True)
    
    class TagListRow(ActionRow):
        def __init__(self, tags: list[Tag]) -> None:
            super().__init__(*[TagListView.TagListEntry(tag) for tag in tags], id=None)
    
    
    def __init__(self, tags: list[Tag], interaction: Interaction, *, timeout: float | None = 600) -> None:
        super().__init__(timeout=timeout)
                    
        self.tags = [
            tags[i:i + TagListView.PAGE_SIZE] 
            for i in range(0, len(tags), TagListView.PAGE_SIZE)
        ]
        self.curr_page = 0
        self.interaction = interaction
        
        self.construct_page()
    
    def construct_page(self) -> None:
        self.clear_items()
        page_tags = self.tags[self.curr_page]
        self.add_item(
            Container(
                TextDisplay(f"## Tags: page {self.curr_page + 1}/{len(self.tags)}"),
                *[TagListView.TagListRow(list(t)) for t in batched(page_tags, 5)],
                TagListActionRow(self),
                accent_colour=APP_COLOUR,
            )
        )
    
    # Only required if this ever becomes not ephemeral: for now it is so i dont care
    # async def interaction_check(self, interaction: Interaction) -> bool:
    #     return interaction.user.id == self.interaction.user.id

    async def change_page(self, increment: int):
        self.curr_page += increment
        self.construct_page()
        await self.interaction.edit_original_response(view=self)

class TagSetModal(Modal):
    tag: Tag | None = None
    
    def __init__(self, tag: Tag | None, *, tag_name: str | None = None, tag_content: str | None = None, timeout: float | None = None, custom_id: str = MISSING) -> None:
        super().__init__(title="Set tag", timeout=timeout, custom_id=custom_id)
        if isinstance(tag, Tag):
            self.tag = tag
            tag_name = tag.name
            tag_content = tag.content
        
        
        self.name_input = TextInput(
            style=TextStyle.short,
            min_length=1,
            max_length=255,
            default=tag_name
        )
        self.add_item(Label(
            text="Tag name",
            component=self.name_input
        ))
        
        self.content_input = TextInput(
            style=TextStyle.long,
            min_length=1,
            placeholder="Content of the tag",
            default=tag_content
        )
        self.add_item(Label(
            text="Tag content",
            component=self.content_input
        ))
    
    async def on_submit(self, interaction: Interaction) -> None:
        self.tag = await create_tag(
            interaction, self.name_input.value, self.content_input.value, self.tag
        )
        await interaction.response.send_message(
            embed=message_embed(f"Tag `{self.tag.name}` created!", description=self.tag.content),
            ephemeral=True,
        )