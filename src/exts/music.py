from __future__ import annotations

# std
import asyncio
import contextlib
from typing import Annotated, Literal, TYPE_CHECKING

# packages
import wavelink
import discord
from discord import app_commands, VoiceChannel
from discord.ext import commands
from common.utils import convert_ms

# local
from common.views import Paginator
from common.source import QueueSource
from common.errors import (
    AlreadyPausedError,
    BadChannel,
    InCommandError,
    IndexTooSmallError,
    InvalidTimeError,
    NoPlayerError,
    NoTrackPlayingError,
    NotInVoiceChannelError,
    NotPausedError,
    QueueEmptyError,
    QueueTooShortError,
)
from common.custom import (
    Context,
    GuildContext,
    Player,
    SeekTime,
)

if TYPE_CHECKING:
    from bot import Advinas


class Music(commands.Cog):
    def __init__(self, bot: Advinas) -> None:
        self.bot = bot

    def is_privileged(self, ctx: GuildContext) -> bool:
        player: Player | None = ctx.voice_client
        return player is not None and ctx.author.guild_permissions.kick_members

    async def cog_check(self, ctx: Context) -> bool:
        if ctx.guild and ctx.guild.id == 590288287864848387:
            if ctx.channel.id not in (*self.bot.BOT_CHANNELS, 666369102981496832):
                raise BadChannel
        return ctx.guild is not None

    def now_playing(
        self,
        player: Player,
        track: wavelink.Playable,
        original: wavelink.Playable | None = None,
    ) -> discord.Embed:
        embed: discord.Embed = discord.Embed(title="Now Playing", url=track.uri)
        embed.color = 60415
        embed.description = f"**{track.title}** by `{track.author}`"
        embed.add_field(
            name="Duration",
            value=convert_ms(player.position) + "/" + convert_ms(track.length),
        )

        if track.artwork:
            embed.set_thumbnail(url=track.artwork)

        if original and original.recommended:
            embed.description += f"\n\n`This track was recommended via {track.source}`"

        if track.album.name:
            embed.add_field(name="Album", value=track.album.name)

        return embed

    @commands.Cog.listener()
    async def on_wavelink_track_start(
        self, payload: wavelink.TrackStartEventPayload
    ) -> None:
        player = payload.player
        if not isinstance(player, Player):
            return

        original: wavelink.Playable | None = payload.original
        track: wavelink.Playable = payload.track

        if player.controller:
            with contextlib.suppress(discord.NotFound):
                await player.controller.delete()

        embed = self.now_playing(player, track, original)
        player.controller = await player.context.send(embed=embed)

    async def join(
        self, ctx: GuildContext, channel: discord.VoiceChannel | None = None
    ) -> Player:
        if channel is None:
            channel = getattr(ctx.author.voice, "channel", None)
            if channel is None:
                raise NotInVoiceChannelError

        player = await channel.connect(cls=Player, self_deaf=True)
        player.autoplay = wavelink.AutoPlayMode.partial
        player.set_context(ctx)
        return player

    @commands.hybrid_command(
        name="join",
        aliases=["j", "summon", "con", "connect"],
        description="Makes the bot join your or the given voice channel.",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        channel="The channel you want the bot to join. Defaults to the channel you are in."
    )
    async def _join(
        self, ctx: GuildContext, *, channel: discord.VoiceChannel | None = None
    ):
        player = await self.join(ctx, channel)
        await ctx.reply(f"Joined the voice channel `{player.channel.name}`.")

    @commands.hybrid_command(
        name="leave",
        aliases=["disconnect", "dc", "stop"],
        description="Makes the bot leave its current voice channel.",
    )
    @app_commands.guild_only()
    async def _leave(self, ctx: GuildContext):
        player: Player | None = ctx.voice_client
        if player is None:
            raise NoPlayerError

        await player.disconnect()
        await ctx.reply("Player has left the channel.")

    @commands.hybrid_command(
        name="play",
        aliases=["pla", "p"],
        description="Plays or queues the given song/songs.",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        search="The song/songs to play, can be a keyword to search or a direct link."
    )
    async def _play(self, ctx: GuildContext, *, search: str):
        player: Player | None = ctx.voice_client
        if player is None:
            player = await self.join(ctx)

        tracks: wavelink.Search = await wavelink.Playable.search(search)
        if not tracks:
            raise InCommandError("No tracks found.")

        if isinstance(tracks, wavelink.Playlist):
            added: int = await player.queue.put_wait(tracks)
            await ctx.reply(
                f"Added the playlist **`{tracks.name}`** ({added} songs) to the queue."
            )
        else:
            track: wavelink.Playable = tracks[0]
            await player.queue.put_wait(track)
            await ctx.reply(f"Added **`{track}`** to the queue.")

        if not player.playing:
            await player.play(player.queue.get())

    @commands.hybrid_command(
        name="autoplay",
        aliases=["ap", "auto"],
        description="Toggles autoplaying songs from youtube at the end of the queue.",
    )
    @app_commands.guild_only()
    async def _autoplay(self, ctx: GuildContext):
        player: Player | None = ctx.voice_client
        if player is None:
            raise NoPlayerError

        if player.autoplay == wavelink.AutoPlayMode.partial:
            player.autoplay = wavelink.AutoPlayMode.enabled
            await ctx.reply("YouTube autoplay is now enabled.")
        else:
            player.autoplay = wavelink.AutoPlayMode.partial
            await ctx.reply("Youtube autoplay is now disabled.")

    @commands.hybrid_command(
        name="reconnect",
        aliases=["rc"],
        description="Reconnects to the channel while saving the current queue (In case the bot dies).",
    )
    @app_commands.guild_only()
    async def _reconnect(self, ctx: GuildContext):
        old_player: Player | None = ctx.voice_client
        if not old_player:
            raise NoPlayerError

        channel: VoiceChannel | None = getattr(ctx.author.voice, "channel", None)
        if not channel:
            raise NotInVoiceChannelError

        volume: int = old_player.volume
        queue: wavelink.Queue = old_player.queue.copy()
        current: wavelink.Playable | None = old_player.current
        if current is not None:
            queue.put_at(0, current)

        await old_player.disconnect()
        await asyncio.sleep(1)

        player = await self.join(ctx, channel)
        player.queue = queue

        await player.play(player.queue.get(), volume=volume)

    @commands.hybrid_command(
        name="nowplaying",
        aliases=["np", "now", "playing"],
        description="Shows the currently playing song.",
    )
    @app_commands.guild_only()
    async def _nowplaying(self, ctx: GuildContext):
        player: Player | None = ctx.voice_client
        if player is None:
            raise NoPlayerError

        track = player.current
        if not isinstance(track, wavelink.Playable):
            raise NoTrackPlayingError

        await ctx.reply(embed=self.now_playing(player, track))

    @commands.hybrid_command(
        name="queue", aliases=["q"], description="Shows the current song queue."
    )
    @app_commands.guild_only()
    async def _queue(self, ctx: GuildContext):
        player: Player | None = ctx.voice_client
        if player is None:
            raise NoPlayerError

        if len(player.queue) < 1:
            raise QueueEmptyError

        entries: list[wavelink.Playable] = list(player.queue)
        await Paginator(QueueSource(entries, ctx.author)).start(ctx)

    @commands.hybrid_command(
        name="loop",
        aliases=["l"],
        description="Changes the loop mode to the given mode.",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        mode="The mode to change the loop mode to. Can be `Song`, `Queue`, or `None`. Changes to next mode if omitted."
    )
    async def _loop(
        self, ctx: GuildContext, mode: Literal["Song", "Queue", "None"] | None = None
    ):
        player: Player | None = ctx.voice_client
        if player is None:
            raise NoPlayerError

        if mode is None:
            current = player.queue.mode
            mode = (
                "Song"
                if current == wavelink.QueueMode.loop
                else "Queue" if current == wavelink.QueueMode.loop_all else "None"
            )
            return await ctx.reply(f"Loop mode is currently set to `{mode}`.")

        modes = {
            "Song": wavelink.QueueMode.loop,
            "Queue": wavelink.QueueMode.loop_all,
            "None": wavelink.QueueMode.normal,
        }

        player.queue.mode = modes[mode]
        await ctx.reply(f"Loop mode set to `{mode}`.")

    @commands.hybrid_command(
        name="remove", aliases=["rm"], description="Removes a song from the queue."
    )
    @app_commands.guild_only()
    @app_commands.describe(
        index="The index of the song that should be removed from the queue (first song = 1)."
    )
    async def _remove(self, ctx: GuildContext, index: int):
        player: Player | None = ctx.voice_client
        if player is None:
            raise NoPlayerError

        if len(player.queue) < 1:
            raise QueueEmptyError
        elif len(player.queue) < index:
            raise QueueTooShortError
        elif index < 1:
            raise IndexTooSmallError

        track = player.queue.peek(index - 1)
        player.queue.delete(index - 1)
        await ctx.reply(f"Removed **{track.title}** from the queue.")

    @commands.hybrid_command(name="pause", description="Pauses the current song.")
    @app_commands.guild_only()
    async def _pause(self, ctx: GuildContext):
        player: Player | None = ctx.voice_client
        if player is None:
            raise NoPlayerError

        if player.paused:
            raise AlreadyPausedError

        await player.pause(True)
        await ctx.reply("The player was paused.")

    @commands.hybrid_command(
        name="resume", aliases=["res", "r"], description="Resume the current song."
    )
    @app_commands.guild_only()
    async def _resume(self, ctx: GuildContext):
        player: Player | None = ctx.voice_client
        if player is None:
            raise NoPlayerError

        if not player.paused:
            raise NotPausedError

        await player.pause(False)
        await ctx.reply("The player was resumed.")

    @commands.hybrid_command(
        name="skip",
        aliases=["s", "next"],
        description="Skips the currently playing song.",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        to="The index of the song that should be skipped to. DEFAULT: 1"
    )
    async def _skip(self, ctx: GuildContext, to: int = 1):
        player: Player | None = ctx.voice_client
        if player is None:
            raise NoPlayerError

        if to < 1:
            raise IndexTooSmallError
        elif to == 1:
            skipped = await player.skip()
            if isinstance(skipped, wavelink.Playable):
                await ctx.reply(f"Skipped **{skipped.title}**.")
            else:
                await ctx.reply("Nothing was skipped.")
            return

        if len(player.queue) < to:
            raise QueueTooShortError

        for _ in range(to - 1):
            del player.queue[0]

        await player.skip()

        if player.current is not None:
            await ctx.reply(f"Skipped to **{player.current.title}**.")
        else:
            await ctx.reply("Skipped to the end of the queue.")

    @commands.hybrid_command(
        name="shuffle", aliases=["mix", "shuf"], description="Shuffles the queue."
    )
    @app_commands.guild_only()
    async def _shuffle(self, ctx: GuildContext):
        player: Player | None = ctx.voice_client
        if player is None:
            raise NoPlayerError

        if len(player.queue) < 1:
            raise QueueEmptyError

        player.queue.shuffle()
        await ctx.reply("The queue was shuffled.")

    @commands.hybrid_command(
        name="volume", aliases=["v", "vol"], description="Changes the players volume."
    )
    @app_commands.guild_only()
    @app_commands.describe(volume="The amount you want to set the volume to.")
    async def _volume(self, ctx: GuildContext, *, volume: float | None = None):
        player: Player | None = ctx.voice_client
        if player is None:
            raise NoPlayerError

        if volume is None:
            return await ctx.reply(
                f"The volume is currently set to **{player.volume}%**."
            )

        vol = int(volume)
        if vol < 0:
            vol = 0
        elif vol > 100:
            vol = 100

        await player.set_volume(vol)
        await ctx.reply(f"Set the volume to **{vol}**%")

    @commands.hybrid_command(
        name="seek",
        aliases=["sk"],
        description="Changes the players position in the song.",
    )
    @app_commands.guild_only()
    @app_commands.describe(time="The time you want to seek to.")
    async def _seek(self, ctx: GuildContext, *, time: Annotated[int | None, SeekTime]):
        player: Player | None = ctx.voice_client
        if player is None:
            raise NoPlayerError

        if time is None:
            raise InvalidTimeError

        time = time * 1000
        await player.seek(time)
        await ctx.reply(f"Set the position to **{convert_ms(time)}**.")


async def setup(bot: Advinas):
    await bot.add_cog(Music(bot))
