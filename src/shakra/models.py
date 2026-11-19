# ty: ignore[invalid-attribute-override]

from enum import IntEnum

from tortoise import Model
from tortoise.fields import (
    BooleanField,
    CharField,
    DatetimeField,
    ForeignKeyField,
    IntEnumField,
    IntField,
    JSONField,
    ReverseRelation,
    TextField,
    UUIDField,
)


class GuildConfig(Model):
    guild_id = IntField(primary_key=True)
    created = DatetimeField(auto_now_add=True)
    touched = DatetimeField(auto_now=True)

    log_channel = IntField(null=True)

    ticket_forum_id = IntField(null=True)
    ticket_tag_id = IntField(null=True)
    appeal_tag_id = IntField(null=True)


class MuteTier(Model):
    guild_id = IntField()
    label = TextField()
    role_id = IntField()

    class Meta:
        unique_together = (("guild_id", "label"), ("guild_id", "role_id"))


class Mute(Model):
    guild_id = IntField()
    user_id = IntField()
    role_id = IntField()

    expiry = DatetimeField()
    created = DatetimeField(auto_now_add=True)

    class Meta:
        unique_together = (("guild_id", "user_id", "role_id"),)


class Ticket(Model):
    id = UUIDField(primary_key=True)
    guild_id = IntField()
    thread_id = IntField()
    user_id = IntField()
    anonymous = BooleanField()

    opened = DatetimeField(auto_now_add=True)
    touched = DatetimeField(auto_now=True)


class Ready(Model):
    id = IntField(primary_key=True)
    ready_count = IntField()


class RaceVCGroup(Model):
    id = UUIDField(primary_key=True)
    guild_id = IntField()
    name = CharField(16)


class RaceVC(Model):
    group_id = ForeignKeyField("models.RaceVCGroup")
    channel_id = IntField()
    isTextChannel = BooleanField()

    class Meta:
        unique_together = (("group_id", "channel_id"),)


class RoleMessageModel(Model):
    message_id = IntField(primary_key=True)

    selectors: ReverseRelation[RoleMessageSelector]


class RoleMessageSelector(Model):
    parent_message = ForeignKeyField("models.RoleMessageModel", "selectors")
    max_roles = IntField()
    roles: JSONField[list[int]] = JSONField()


class TagContext(IntEnum):
    GUILD = 0
    USER = 1


class TagLabelStyle(IntEnum):
    NONE = 0
    PREFIX = 1
    BUTTON = 2


class Tag(Model):
    parent_id = IntField()
    """Guild ID if context is GUILD, User ID if context is USER"""
    context = IntEnumField(TagContext)
    name = TextField()
    content = TextField()

    class Meta:
        unique_together = (("parent_id", "context", "name"),)
        ordering = ["name"]  # noqa: RUF012


class TagDisplayConfig(Model):
    parent_id = IntField()
    context = IntEnumField(TagContext)
    style = IntEnumField(TagLabelStyle)

    class Meta:
        unique_together = ("parent_id", "context")


class SrRoleEntry(Model):
    guild_id = IntField()
    role_id = IntField()
    game_id = CharField(10)

    class Meta:
        unique_together = (("guild_id", "role_id", "game_id"),)


class SrcTrackingChannel(Model):
    guild_id = IntField()
    channel_id = IntField()
    game_id = CharField(10)
    
    class Meta:
        unique_together = (("guild_id", "channel_id", "game_id"),)


class HKCLiveRole(Model):
    guild_id = IntField(primary_key=True)
    role_id = IntField()