from __future__ import annotations

# std
import re
import traceback
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, TYPE_CHECKING

# packages
import wavelink
import discord
from discord.ext import commands
from discord.ext.commands import BadArgument, CheckFailure

# local
from common.utils import codeblock, convert_seconds

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


class Player(wavelink.Player):
    """Custom wavelink Player class."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        self.controller: discord.Message | None = None
        self.context: Context
        self.dj: discord.Member
        self.loop_mode: Literal['Song', 'Queue'] | None = None

    def now_playing(self, track: wavelink.YouTubeTrack, *, new: bool = False) -> discord.Embed:
        if track.is_stream():
            title = f":red_circle: **LIVE** {track.title}"
        else:
            title = track.title
        embed = discord.Embed(
            title=title, description=f'Duration: {convert_seconds(self.position if not new else 0)}/{convert_seconds(track.length)}', url=track.uri
        ).set_footer(text=f'Author: {track.author}', icon_url=track.thumbnail)
        return embed.set_thumbnail(url=track.thumbnail)

    async def do_next(self) -> None:
        if self.controller:
            with suppress(discord.HTTPException):
                await self.controller.delete()

        try:
            track: wavelink.YouTubeTrack = self.queue.get()  # type: ignore
        except wavelink.QueueEmpty:
            return  # await self.teardown()

        if self.loop_mode == 'Queue':
            self.queue.put(track)

        await self.play(track)
        if hasattr(self, 'context'):
            self.controller = await self.context.send(embed=self.now_playing(track, new=True))

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

    async def convert(self, ctx: Context, argument: str) -> int | None:
        """Converts the given time into seconds."""
        match = self.compiled.fullmatch(argument)
        if match is None or not match.group(0):
            await ctx.reply('The provided time is invalid.')
            await ctx.log('Invalid time provided.')
            return

        data = {k: int(v) for k, v in match.groupdict(default=0).items()}
        return data.get('hours', 0) * 3600 + data.get('minutes', 0) * 60 + data.get('seconds', 0)


class Context(commands.Context['Advinas']):
    """Custom Context class for easier logging."""

    @property
    def voice_client(self) -> Player | None:
        return super().voice_client  # type: ignore

    @property
    def _command_name(self) -> str:
        return self.command.name if self.command else 'Unknown'

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
            inline=True
        ).add_field(
            name='**Channel**',
            value=f'`{self.channel}` in `{self.guild.name if self.guild else "DM"}`',
            inline=True
        ).add_field(
            name='**Prefix**',
            value=f'`{self.prefix}`',
            inline=False
        ).add_field(
            name='**Command**',
            value=f'`{self._command_name.title()}`',
            inline=True
        ).add_field(
            name='**Arguments**',
            value=' '.join([f'`{a}`' for a in self.args[2:]]) or 'None',
            inline=False
        ).add_field(
            name='**Keyword Arguments**',
            value=' '.join(
                [f'`{k}={v}`' for k, v in self.kwargs.items()]) or 'None',
            inline=False)
        if self.interaction is None:
            em.add_field(
                name='**Message**',
                value=f'`{self.message.content}`',
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
            name='**Channel**',
            value=f'`{self.channel}` in `{self.guild.name if self.guild else "DM"}`',
            inline=True
        ).add_field(
            name='**Prefix**',
            value=f'`{self.prefix}`',
            inline=False
        ).add_field(
            name='**Command**',
            value=f'`{self._command_name.title()}`',
            inline=True
        ).add_field(
            name='**Arguments**',
            value=' '.join([f'`{a}`' for a in self.args[2:]]) or 'None',
            inline=False
        ).add_field(
            name='**Keyword Arguments**',
            value=' '.join(
                [f'`{k}={v}`' for k, v in self.kwargs.items()]) or 'None',
            inline=False)
        if self.interaction is None:
            em.add_field(
                name='**Message**',
                value=f'`{self.message.content}`',
                inline=False
            )
        em.add_field(
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


class SyntheticQueue:
    def __init__(self, queue: wavelink.WaitQueue) -> None:
        self.tracks = queue
        self.name = str(len(queue)) + ' tracks'


class SongConverter(commands.Converter):
    async def convert(self, ctx: Context, song: str | SyntheticQueue) -> wavelink.YouTubeTrack | wavelink.YouTubePlaylist | SyntheticQueue:
        if isinstance(song, SyntheticQueue):
            return song
        track = await wavelink.YouTubeTrack.search(song)
        if track:
            return track[0]
        playlist = await wavelink.YouTubePlaylist.search(song)
        if not playlist:
            raise BadArgument("Invalid song provided.")
        return playlist  # type: ignore


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
