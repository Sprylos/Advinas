from __future__ import annotations

# std
import io
import re
import traceback
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TYPE_CHECKING

# packages
import wavelink
import discord
from discord.ext import commands

# local
from common.utils import codeblock, convert_ms
from common.errors import BadChannel, BadLevel

if TYPE_CHECKING:
    from bot import Advinas


def check_channel(*channel_ids: int):
    async def predicate(ctx: Context) -> bool:
        if ctx.guild and ctx.guild.id == 590288287864848387:
            if ctx.channel.id not in (*ctx.bot.BOT_CHANNELS, *channel_ids):
                raise BadChannel
        return True

    return commands.check(predicate)


def app_check_channel(*channel_ids: int):
    async def predicate(inter: discord.Interaction) -> bool:
        if inter.guild and inter.guild.id == 590288287864848387:
            if inter.channel and inter.channel.id not in (*inter.client.BOT_CHANNELS, *channel_ids):  # type: ignore # nopep8
                raise BadChannel
        return True

    return discord.app_commands.check(predicate)


class Player(wavelink.Player):
    """Custom wavelink Player class."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        self.controller: discord.Message | None = None
        self.context: Context
        self.dj: discord.Member

    def now_playing(
        self, track: wavelink.Playable, *, new: bool = False
    ) -> discord.Embed:
        if track.is_stream:
            title = f":red_circle: **LIVE** {track.title}"
        else:
            title = track.title
        thumbnail = getattr(track, "thumbnail", None)
        embed = discord.Embed(
            title=title,
            description=f"Duration: {convert_ms(self.position if not new else 0)}/{convert_ms(track.length)}",
            url=track.uri,
        ).set_footer(text=f"Author: {track.author}", icon_url=thumbnail)
        return embed.set_thumbnail(url=thumbnail)

    async def do_next(self) -> None:
        if self.controller:
            with suppress(discord.HTTPException):
                await self.controller.delete()

        try:
            track: wavelink.YouTubeTrack = self.queue.get()  # type: ignore
        except wavelink.QueueEmpty:
            return  # await self.teardown()

        await self.play(track)
        if hasattr(self, "context"):
            self.controller = await self.context.send(
                embed=self.now_playing(track, new=True)
            )

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
        argument = argument.replace(" ", "")

        if ":" in argument:
            try:
                return sum(
                    int(i) * 60**index
                    for index, i in enumerate(argument.split(":")[::-1])
                )
            except ValueError:
                pass

        match = self.compiled.fullmatch(argument)
        if match is None or not match.group(0):
            return None

        data = {k: int(v) for k, v in match.groupdict(default=0).items()}
        return (
            data.get("hours", 0) * 3600
            + data.get("minutes", 0) * 60
            + data.get("seconds", 0)
        )


class Context(commands.Context["Advinas"]):
    """Custom Context class for easier logging."""

    @property
    def voice_client(self) -> Player | None:
        return super().voice_client  # type: ignore

    @property
    def _command_name(self) -> str:
        return self.command.name if self.command else "Unknown"

    async def log(self, reason: str | None = None, /, *, success: bool | None = None):
        """Logs the usage of commands. Should be called at the end of any command."""

        success = (
            success if success is not None else (True if reason is None else False)
        )

        color = discord.Color.green() if success else discord.Color.red()

        em = (
            discord.Embed(
                title=f"**{self._command_name} Command** used in `{self.channel}`",
                colour=color,
            )
            .set_footer(
                text=f"Command run by {self.author}",
                icon_url=self.author.display_avatar.url,
            )
            .add_field(name="**Success**", value=f"`{success}`", inline=True)
            .add_field(
                name="**Channel**",
                value=f'`{self.channel}` in `{self.guild.name if self.guild else "DM"}`',
                inline=True,
            )
            .add_field(name="**Prefix**", value=f"`{self.prefix}`", inline=False)
            .add_field(name="**Command**", value=f"`{self._command_name}`", inline=True)
            .add_field(
                name="**Arguments**",
                value=" ".join([f"`{a}`" for a in self.args[2:]])[:1020] or "None",
                inline=False,
            )
            .add_field(
                name="**Keyword Arguments**",
                value=" ".join([f"`{k}={v}`" for k, v in self.kwargs.items()])[:1020]
                or "None",
                inline=False,
            )
        )
        if self.interaction is None:
            em.add_field(
                name="**Message**",
                value=f"`{self.message.content[:1020]}`",
                inline=False,
            )
        if reason:
            em.add_field(name="**Reason**", value=f"`{reason[:1020]}`", inline=False)
        await self.bot._log.send(embed=em)

    async def trace(self, err: Exception):
        """Called when an unhandled Exception occurs to inform me about the issue."""

        tb = codeblock(
            " ".join(["Error occured in command", self._command_name, "\n"])
            + "".join(traceback.format_exception(type(err), err, err.__traceback__))
        )
        if len(tb) > 1990:
            await self.bot._trace.send(codeblock(tb[3:1990]))
            await self.bot._trace.send(codeblock(tb[1990:-3]))
            tb = "Too long"
        elif len(tb) > 1000:
            await self.bot._trace.send(tb)
            tb = "Too long"
        em = (
            discord.Embed(
                title=f"**{self._command_name} Command** used in `{self.channel}`",
                colour=discord.Color.red(),
            )
            .set_footer(
                text=f"Command run by {self.author}",
                icon_url=self.author.display_avatar.url,
            )
            .add_field(
                name="**Channel**",
                value=f'`{self.channel}` in `{self.guild.name if self.guild else "DM"}`',
                inline=True,
            )
            .add_field(name="**Prefix**", value=f"`{self.prefix}`", inline=False)
            .add_field(name="**Command**", value=f"`{self._command_name}`", inline=True)
            .add_field(
                name="**Arguments**",
                value=" ".join([f"`{a}`" for a in self.args[2:]]) or "None",
                inline=False,
            )
            .add_field(
                name="**Keyword Arguments**",
                value=" ".join([f"`{k}={v}`" for k, v in self.kwargs.items()])
                or "None",
                inline=False,
            )
        )
        if self.interaction is None:
            em.add_field(
                name="**Message**", value=f"`{self.message.content}`", inline=False
            )
        em.add_field(name="**Traceback**", value=tb, inline=False)
        await self.bot._trace.send(embed=em)

    async def safe_send(self, content: str, **kwargs: Any) -> discord.Message:
        if len(content) > 2000:
            fp = io.BytesIO(content.encode())
            kwargs.pop("file", None)
            return await self.send(
                file=discord.File(fp, filename="too_long.txt"), **kwargs
            )
        else:
            return await self.send(content, **kwargs)


class GuildContext(Context):
    author: discord.Member
    guild: discord.Guild
    channel: discord.VoiceChannel | discord.TextChannel | discord.Thread
    me: discord.Member


class LevelConverter(commands.Converter):
    async def convert(self, ctx: Context, level: str) -> str:
        level = (
            level.replace("_", ".")
            .replace(",", ".")
            .replace("-", ".")
            .replace(" ", ".")
            .lower()
        )
        if not (level in ctx.bot.LEVELS):
            raise BadLevel
        if level.startswith("dq"):
            level = level.upper()
        return level


class SyntheticQueue:
    def __init__(self, queue: wavelink.BaseQueue) -> None:
        self.tracks = queue
        self.name = str(len(queue)) + " tracks"


class SongConverter(commands.Converter):
    async def convert(
        self, ctx: Context, song: str | SyntheticQueue
    ) -> wavelink.SoundCloudTrack | wavelink.YouTubeTrack | wavelink.YouTubePlaylist | SyntheticQueue:
        if isinstance(song, SyntheticQueue):
            return song
        song = song.strip("<>")
        if "soundcloud.com" in song:
            track = await wavelink.SoundCloudTrack.search(song)
            if not track:
                raise commands.BadArgument("Could not find track.")
            return track[0]
        if "youtube.com" in song:
            node = wavelink.NodePool.get_node()
            try:
                tracks = await node.get_tracks(wavelink.YouTubeTrack, song)
            except (wavelink.InvalidLavalinkResponse, ValueError):
                tracks = None
            if tracks:
                return tracks[0]
            try:
                playlist = await wavelink.YouTubePlaylist.search(song)
            except (wavelink.InvalidLavalinkResponse, ValueError):
                raise commands.BadArgument("Could not find track.")
            if not playlist:
                raise commands.BadArgument("Could not find track.")
            return playlist  # type: ignore
        tracks = await wavelink.YouTubeTrack.search(song)
        if tracks:
            return tracks[0]
        else:
            try:
                playlist = await wavelink.YouTubePlaylist.search(song)
            except (wavelink.InvalidLavalinkResponse, ValueError):
                raise commands.BadArgument("Could not find track.")
            if not playlist:
                raise commands.BadArgument("Could not find track.")
            return playlist  # type: ignore


class TagName(commands.clean_content):
    def __init__(self, *, lower: bool = True):
        self.lower = lower
        super().__init__()

    async def convert(self, ctx: Context, argument: str) -> str:
        converted = await super().convert(ctx, argument)
        lower = converted.lower().strip().replace("\n", "")

        if not lower:
            raise commands.BadArgument("Missing tag name.")

        if len(lower) > 100:
            raise commands.BadArgument("Tag name is a maximum of 100 characters.")

        first_word, _, _ = lower.partition(" ")

        # get tag command.
        root = ctx.bot.get_command("tag")
        if isinstance(root, commands.Group):
            if first_word in root.all_commands:
                raise commands.BadArgument("This tag name starts with a reserved word.")

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
        t: dict[str, Any] = payload["tags"][0]
        guild = int(payload["guild"])
        return cls(
            t["name"],
            t["content"],
            guild,
            int(t["uses"]),
            int(t["owner_id"]),
            t["created_at"],
        )

    @classmethod
    def minimal(cls, name: str, guild: int) -> Tag:
        return cls(name, "", guild, 0, 0, datetime.now())


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
        t: dict[str, Any] = payload["tags"][0]
        guild = int(payload["guild"])
        return cls(t["name"], t["alias"], guild, int(t["owner_id"]), t["created_at"])
