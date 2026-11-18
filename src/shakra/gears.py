from enum import Enum

from discord import Interaction
from discord.app_commands import Command as SlashCmd
from discord.app_commands import ContextMenu, command
from discord.ext.commands import Cog
from discord.ext.commands import Command as TextCmd
from tortoise import Model
from tortoise.fields import BooleanField, CharField, IntField

COMMAND = SlashCmd | TextCmd | ContextMenu


class Scope(Enum):
    GLOBAL = 0
    LOCAL = 1

class GuildGearConfig(Model):
    guild_id = IntField()
    gear_id = CharField(32)
    enabled = BooleanField()
    
    class Meta:  # ty: ignore[invalid-attribute-override]
        unique_together = (("guild_id", "gear_id"), )
        ordering = ["name"]  # noqa: RUF012

class Gear:
    __registered_locals: set[COMMAND]
    __registered_globals: set[COMMAND]
    
    def __init__(self) -> None:
        self.__registered_locals = set()
        self.__registered_globals = set()
        # Behold; the jankiest hack ever to make this work
        for member in self.__class__.__dict__.values():
            if not isinstance(member, (SlashCmd, TextCmd, ContextMenu)): continue
            if member.extras.get("scope.global", False): 
                self.__registered_globals.add(member)
            if member.extras.get("scope.local", False): 
                self.__registered_locals.add(member)
    
    
    
    
    
            
    
def local_cmd():
    """Indicates a command should be applied to local Shakra contexts."""
    def decorator(cmd: SlashCmd | TextCmd | ContextMenu):
        cmd.extras["scope.local"] = True
        return cmd
    
    return decorator

def global_cmd():
    """Indicates a command should be applied to the global Shakra context."""
    def decorator(cmd: SlashCmd | TextCmd | ContextMenu):
        cmd.extras["scope.global"] = True
        return cmd
    
    return decorator

class TestGear(Cog, Gear, name="Test"):
    @local_cmd()
    @command()
    async def mycommand(self, interaction: Interaction):
        ...

__all__ = [
    "Gear",
    "GuildGearConfig",
    "global_cmd",
    "local_cmd"
]
