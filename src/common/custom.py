from __future__ import annotations

# std
import traceback
from dataclasses import dataclass
from datetime import datetime
from typing import (
    Any,
    Dict,
    Optional,
)

# packages
from discord import Color, Embed
from discord.ext import commands
from discord.ext.commands.errors import BadArgument, CheckFailure

# local
from common.utils import codeblock


class BadLevel(BadArgument):
    """Exception raised when the provided level is not valid."""
    pass


class BadChannel(CheckFailure):
    """Exception raised when the message channel is not an allowed channel."""
    pass


class TagError(RuntimeError):
    """Raised for internal tag errors that should be ignored by the global error handler."""
    pass


class Context(commands.Context):
    """Custom Context class for easier logging."""

    @property
    def _command_name(self) -> str:
        return self.command.name  # type: ignore

    @property
    def _invoked_arguments(self) -> str:
        command = self._command_name

        if self.invoked_parents:
            command = ' '.join(self.invoked_parents) + ' ' + command

        return f'`{self.prefix or "/"}{command}` ' + ' '.join([f'`{k}={v}`' for k, v in self.kwargs.items()])

    async def log(self, reason: Optional[str] = None, /, *, success: Optional[bool] = None):
        """Logs the usage of commands. Should be called at the end of any command."""

        success = success if success is not None else (
            True if reason is None else False)

        color = Color.green() if success else Color.red()

        em = Embed(
            title=f"**{self._command_name.title()} Command** used in `{self.channel}`", colour=color
        ).set_footer(
            text=f"Command run by {self.author}",
            icon_url=self.author.display_avatar.url
        ).add_field(
            name='**Success**',
            value=f'`{success}`',
            inline=False
        ).add_field(
            name='**Arguments**',
            value=self._invoked_arguments,
            inline=False
        )
        if reason:
            em.add_field(
                name='**Reason**',
                value=f'`{reason}`',
                inline=False
            )
        await self.bot._log.send(embed=em)

    async def trace(self, err: Exception):
        """Called when an unhandled Exception occurs to inform me about the issue."""

        tb = codeblock(' '.join(['Error occured in command', self._command_name, '\n']) + ''.join(
            traceback.format_exception(type(err), err, err.__traceback__)))
        if len(tb) > 1990:
            await self.bot._trace.send(codeblock(tb[3:1990]))
            await self.bot._trace.send(codeblock(tb[1990:-3]))
            tb = 'long lol'
        elif len(tb) > 1000:
            await self.bot._trace.send(tb)
            tb = tb[:1000] + '```'
        em = Embed(
            title=f"**{self._command_name.title()} Command** used in `{self.channel}`", colour=Color.red()
        ).set_footer(
            text=f"Command run by {self.author}",
            icon_url=self.author.display_avatar.url
        ).add_field(
            name='**Content**',
            value=self._invoked_arguments,
            inline=False
        ).add_field(
            name='**Traceback**',
            value=tb,
            inline=False
        )
        await self.bot._trace.send(embed=em)


class LevelConverter(commands.Converter):
    async def convert(self, ctx: Context, level: str) -> str:
        level = level.replace('_', '.').replace(
            ',', '.').replace('-', '.').replace(' ', '.').lower()
        if not (level in ctx.bot.LEVELS):
            raise BadLevel("Invalid level provided.")
        if level.startswith('dq'):
            level = level.upper()
        return level


class TagName(commands.clean_content):
    def __init__(self, *, lower: bool = True):
        self.lower = lower
        super().__init__()

    async def convert(self, ctx: Context, argument: str) -> str:
        converted = await super().convert(ctx, argument)
        lower = converted.lower().strip()

        if not lower:
            raise commands.BadArgument('Missing tag name.')

        if len(lower) > 100:
            raise commands.BadArgument(
                'Tag name is a maximum of 100 characters.')

        first_word, _, _ = lower.partition(' ')

        # get tag command.
        root = ctx.bot.get_command('tag')
        if first_word in root.all_commands:
            raise commands.BadArgument(
                'This tag name starts with a reserved word.')

        return converted if not self.lower else lower


@dataclass
class Tag:
    name: str
    content: str
    guild_id: int
    uses: int
    owner_id: int
    created_at: datetime

    @classmethod
    def from_db(cls, payload: Dict[str, Any]) -> Tag:
        """Creates a new Tag object with the given database payload."""
        t: Dict[str, Any] = payload['tags'][0]
        guild = int(payload['guild'])
        return cls(t['name'], t['content'], guild, int(t['uses']), int(t['owner_id']), t['created_at'])

    @classmethod
    def minimal(cls, name: str, guild: int) -> Tag:
        return cls(name, '', guild, 0, 0, datetime.now())
