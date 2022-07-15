from __future__ import annotations

# std
import re
import traceback
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, TYPE_CHECKING

# packages
import pomice
import discord
from discord.ext import commands
from discord.ext.commands import BadArgument, CheckFailure

# local
from common.utils import codeblock

if TYPE_CHECKING:
    from bot import Advinas


class BadLevel(BadArgument):
    """Exception raised when the provided level is not valid."""
    pass


class BadChannel(CheckFailure):
    """Exception raised when the message channel is not an allowed channel."""
    pass


class TagError(RuntimeError):
    """Raised for internal tag errors that should be ignored by the global error handler."""
    pass


class NoPlayerError(RuntimeError):
    """Raised when the bot is not in a voice channel."""
    pass


class PlayerNotConnectedError(RuntimeError):
    """Raised when the player is not connected."""
    pass


class Player(pomice.Player):
    """Custom pomice Player class."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        self.queue: list[pomice.Track] = []
        self.controller: discord.Message | None = None
        self.context: Context
        self.dj: discord.Member
        self.loop_mode: Literal['Song', 'Queue'] | None = None

    async def do_next(self) -> None:
        if self.controller:
            with suppress(discord.HTTPException):
                await self.controller.delete()

        try:
            track: pomice.Track = self.queue.pop(0)
        except IndexError:
            return  # await self.teardown()
        else:
            if self.loop_mode == 'Queue':
                self.queue.append(track)

        await self.play(track)

        requester = track.requester
        mention = requester.mention if requester else '@Invalid User'
        if track.is_stream:
            description = f":red_circle: **LIVE** [{track.title}]({track.uri}) [{mention}]"
        else:
            description = f"[{track.title}]({track.uri}) [{mention}]"
        embed = discord.Embed(title=f"Now playing", description=description)
        embed.set_thumbnail(url=track.thumbnail)
        if hasattr(self, 'context'):
            self.controller = await self.context.send(embed=embed)

    async def teardown(self):
        with suppress((discord.HTTPException), (KeyError)):
            await self.destroy()
            if self.controller:
                await self.controller.delete()

    def set_context(self, ctx: Context):
        self.context = ctx
        # always in guild
        if isinstance(ctx.author, discord.Member):
            self.dj = ctx.author


class SeekTime(commands.Converter):
    compiled = re.compile(
        """
           (?:(?P<hours>[0-9]{1,5})(?:hours?|h))?        # e.g. 12h
           (?:(?P<minutes>[0-9]{1,5})(?:minutes?|m))?    # e.g. 10m
           (?:(?P<seconds>[0-9]{1,5})(?:seconds?|s))?    # e.g. 15s
        """,
        re.VERBOSE,
    )

    async def convert(self, ctx: Context, argument: str):
        """Converts the given time into seconds."""
        match = self.compiled.fullmatch(argument)
        if match is None or not match.group(0):
            await ctx.reply('The provided time is invalid.')
            return await ctx.log('Invalid time provided.')

        data = {k: int(v) for k, v in match.groupdict(default=0).items()}
        return data.get('hours', 0) * 3600 + data.get('minutes', 0) * 60 + data.get('seconds', 0)


class Context(commands.Context['Advinas']):
    """Custom Context class for easier logging."""

    @property
    def voice_client(self) -> Player | None:
        return super().voice_client  # type: ignore

    @property
    def _command_name(self) -> str:
        return self.command.name  # type: ignore

    @property
    def _invoked_arguments(self) -> str:
        command = self._command_name

        if self.invoked_parents:
            command = ' '.join(self.invoked_parents) + ' ' + command

        return f'`{self.prefix or "/"}{command}` ' + ' '.join([f'`{k}={v}`' for k, v in self.kwargs.items()])

    async def log(self, reason: str | None = None, /, *, success: bool | None = None):
        """Logs the usage of commands. Should be called at the end of any command."""

        success = success if success is not None else (
            True if reason is None else False)

        color = discord.Color.green() if success else discord.Color.red()

        em = discord.Embed(
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
            tb = 'Too long'
        elif len(tb) > 1000:
            await self.bot._trace.send(tb)
            tb = 'Too long'
        em = discord.Embed(
            title=f"**{self._command_name.title()} Command** used in `{self.channel}`", colour=discord.Color.red()
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
        lower = converted.lower().strip().replace('\n', '')

        if not lower:
            raise commands.BadArgument('Missing tag name.')

        if len(lower) > 100:
            raise commands.BadArgument(
                'Tag name is a maximum of 100 characters.')

        first_word, _, _ = lower.partition(' ')

        # get tag command.
        root = ctx.bot.get_command('tag')
        if isinstance(root, commands.HybridGroup):
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
    def from_db(cls, payload: dict[str, Any]) -> Tag:
        """Creates a new Tag object with the given database payload."""
        t: dict[str, Any] = payload['tags'][0]
        guild = int(payload['guild'])
        return cls(t['name'], t['content'], guild, int(t['uses']), int(t['owner_id']), t['created_at'])

    @classmethod
    def minimal(cls, name: str, guild: int) -> Tag:
        return cls(name, '', guild, 0, 0, datetime.now())


@dataclass
class TagAlias:
    name: str
    alias: str
    guild_id: int
    owner_id: int
    created_at: datetime

    @classmethod
    def from_db(cls, payload: dict[str, Any]) -> TagAlias:
        """Creates a new TagAlias object with the given database payload."""
        t: dict[str, Any] = payload['tags'][0]
        guild = int(payload['guild'])
        return cls(t['name'], t['alias'], guild, int(t['owner_id']), t['created_at'])
