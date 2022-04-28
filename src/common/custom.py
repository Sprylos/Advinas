from __future__ import annotations

# std
import traceback
from dataclasses import dataclass
from datetime import datetime
from typing import (
    Dict,
    List,
    Optional,
    Union
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
    '''Raised for internal tag errors that should be ignored by the global error handler.'''
    pass


class Context(commands.Context):
    """Custom Context class for easier logging."""

    async def log(self, reason: Optional[str] = None, /, *, success: Optional[bool] = None):
        '''Logs the usage of commands. Should be called at the end of any command.'''

        success = success if success is not None else (
            True if reason is None else False)

        command = self.command.name.lower()  # type: ignore
        print(self.args)
        args = [str(arg) for arg in self.args[1:]]
        content = ' '.join(args) if args and args[0] is not None else ''

        value = f'`/{command.lower()}` `{content}`' if content else f'`/{command.lower()}`'

        color = Color.green() if success else Color.red()

        em = Embed(
            title=f"**{command.title()} Command** used in `{self.channel}`", colour=color
        ).set_footer(
            text=f"Command run by {self.author}",
            icon_url=self.author.display_avatar.url
        ).add_field(
            name='**Success**',
            value=f'`{success}`',
            inline=False
        ).add_field(
            name='**Arguments**',
            value=value,
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
        '''Called when an unhandled Exception occurs to inform me about the issue.'''

        command = self.command.name.lower()  # type: ignore
        args = [str(arg) for arg in self.args[1:]]
        content = ' '.join(args) if args and args[0] is not None else ''

        tb = codeblock(' '.join(['Error occured in command', command, '\n']) + ''.join(
            traceback.format_exception(type(err), err, err.__traceback__)))
        if len(tb) > 1990:
            await self.bot._trace.send(codeblock(tb[2:1990]))
            await self.bot._trace.send(codeblock(tb[1990:-2]))
            tb = 'long lol'
        elif len(tb) > 1000:
            await self.bot._trace.send(tb)
            tb = tb[:1000] + '```'
        em = Embed(
            title=f"**{command.title()} Command** used in `{self.channel}`", colour=Color.red()
        ).set_footer(
            text=f"Command run by {self.author}",
            icon_url=self.author.display_avatar.url
        ).add_field(
            name='**Content**',
            value=f'`/{command}` `{content}`' if content else f'`/{command}`',
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
    def from_db(cls, payload: Dict[str, Union[str, List[Dict[str, str]]]]) -> Tag:
        '''
        Example paylod:
        {
            'guild': 796313079708123147, 
            'tags': [
                {'name': 'hi', 'content': 'Hello!', 'uses': 0, 
                'owner_id': 592488492085411840, 'created_at': 'Wed Apr  6 12:27:24 2022'}
            ]
        }
        '''
        t: Dict[str, str] = payload['tags'][0]  # type: ignore
        guild = int(payload['guild'])  # type: ignore
        return cls(t['name'], t['content'], guild, int(t['uses']), int(t['owner_id']), datetime.strptime(t['created_at'], '%c'))

    @classmethod
    def minimal(cls, name: str, guild: int) -> Tag:
        return cls(name, '', guild, 0, 0, datetime.now())
