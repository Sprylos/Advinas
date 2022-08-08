from __future__ import annotations

# std
import random
from typing import Annotated, Any, Literal, TYPE_CHECKING

# packages
import wavelink
import discord
from discord import app_commands, ClientException, VoiceChannel
from discord.ext import commands
from common.utils import convert_seconds

# local
from config import host, port, password
from common.views import Paginator
from common.source import QueueSource
from common.custom import (
    BadChannel,
    Context,
    NoPlayerError,
    Player,
    PlayerNotConnectedError,
    SeekTime,
    SongConverter,
    SyntheticQueue,
)

if TYPE_CHECKING:
    from bot import Advinas


class Music(commands.Cog):
    def __init__(self, bot: Advinas) -> None:
        self.bot = bot
        self.wavelink = wavelink.NodePool()

        bot.loop.create_task(self.start_nodes())

    async def start_nodes(self):
        await self.bot.wait_until_ready()
        await self.wavelink.create_node(
            bot=self.bot,
            host=host,
            port=int(port),
            password=password,
            identifier="MAIN"
        )

    def is_privileged(self, ctx: Context) -> bool:
        player: Player | None = ctx.voice_client
        # always in guild
        return player and player.dj == ctx.author or ctx.author.guild_permissions.kick_members  # type: ignore

    async def cog_check(self, ctx: Context) -> bool:
        if ctx.guild and ctx.guild.id == 590288287864848387:
            if ctx.channel.id not in (*self.bot.BOT_CHANNELS, 666369102981496832):
                raise BadChannel('Command not used in an allowed channel.')
        return not not ctx.guild  # True if used in a guild

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, player: Player, track: wavelink.YouTubeTrack, reason: Literal['FINISHED', 'REPLACED', 'CLEANUP', 'LOAD_FAILED']) -> None:
        if reason in ('REPLACED', 'LOAD_FAILED'):
            return
        if player.loop_mode == 'Song':
            player.queue.put_at_front(track)
        elif player.loop_mode == 'Queue':
            player.queue.put(track)
        await player.do_next()

    @commands.Cog.listener()
    async def on_wavelink_track_stuck(self, player: Player, track: wavelink.YouTubeTrack, **_: Any) -> None:
        await player.do_next()

    @commands.Cog.listener()
    async def on_wavelink_track_exception(self, player: Player, track: wavelink.YouTubeTrack, **_: Any) -> None:
        await player.do_next()

    async def join(self, ctx: Context, channel: discord.VoiceChannel | None = None) -> Player | None:
        if not channel:
            channel = getattr(ctx.author.voice, 'channel', None)  # type: ignore # nopep8
            if not channel:
                await ctx.reply('You must be in a voice channel in order to use this command!')
                return await ctx.log('Member not in a voice channel.')

        try:
            player = await channel.connect(cls=Player)
        except ClientException as e:
            await ctx.reply(str(e))
            return await ctx.log(str(e))
        player.set_context(ctx)
        return player

    @commands.hybrid_command(name='join', aliases=['j', 'summon', 'con', 'connect'], description='Makes the bot join your or the given voice channel.')
    @app_commands.guild_only()
    @app_commands.describe(channel='The channel you want the bot to join. Defaults to the channel you are in.')
    async def _join(self, ctx: Context, *, channel: discord.VoiceChannel | None = None):
        player = await self.join(ctx, channel)
        if player is None:
            return
        await ctx.reply(f'Joined the voice channel `{player.channel.name}`.')

    @commands.hybrid_command(name='leave', aliases=['disconnect', 'dc', 'stop'], description='Makes the bot leave its current voice channel.')
    @app_commands.guild_only()
    async def _leave(self, ctx: Context):
        player: Player | None = ctx.voice_client
        if player is None:
            raise NoPlayerError('Bot is not connected.')
        await player.disconnect()
        await ctx.reply("Player has left the channel.")

    @commands.hybrid_command(name='play', aliases=['pla', 'p'], description='Plays or queues the given song/songs.')
    @app_commands.guild_only()
    @app_commands.describe(search='The song/songs to play, can be a keyword to search or a direct link.')
    async def _play(self, ctx: Context, *, search: Annotated[wavelink.SoundCloudTrack | wavelink.YouTubeTrack | wavelink.YouTubePlaylist | SyntheticQueue, SongConverter]):
        player: Player | None = ctx.voice_client
        if player is None:
            player = await self.join(ctx)
            if player is None:
                return

        if isinstance(search, wavelink.YouTubePlaylist | SyntheticQueue):
            queued = search.name
            for track in search.tracks:
                player.queue.put(track)
            player.loop_mode = getattr(search, 'loop', None)
        else:
            queued = search.title
            player.queue.put(search)

        if not player.is_playing():
            await player.do_next()
        if len(player.queue) > 0:
            await ctx.reply(f'Queued **{queued}**.')

    @commands.hybrid_command(name='reconnect', aliases=['rc'], description='Reconnects to the channel while saving the current queue (In case the bot dies).')
    @app_commands.guild_only()
    async def _reconnect(self, ctx: Context):
        old_player: Player | None = ctx.voice_client
        if not old_player:
            raise NoPlayerError('Bot is not in voice channel.')
        if not old_player.is_connected():
            raise PlayerNotConnectedError('Bot is not connected.')

        channel: VoiceChannel | None = getattr(ctx.author.voice, 'channel', None)  # type: ignore # nopep8
        if not channel:
            await ctx.reply('You must be in a voice channel in order to use this command!')
            return await ctx.log('Member not in a voice channel.')

        current = old_player.source
        queue = old_player.queue.copy()
        loop = old_player.loop_mode
        await old_player.disconnect()
        if current is not None:
            queue.put_at_front(current)
        await ctx.invoke(self._play, search=SyntheticQueue(queue, loop))

    @commands.hybrid_command(name='nowplaying', aliases=['np', 'now', 'playing'], description='Shows the currently playing song.')
    @app_commands.guild_only()
    async def _nowplaying(self, ctx: Context):
        player: Player | None = ctx.voice_client
        if player is None:
            raise NoPlayerError('Bot is not in voice channel.')
        if not player.is_connected():
            raise PlayerNotConnectedError('Bot is not connected.')
        track = player.source
        if not isinstance(track, wavelink.YouTubeTrack):
            await ctx.reply('No track is currently playing.')
            return await ctx.log('No track is currently playing.')
        await ctx.reply(embed=player.now_playing(track))

    @commands.hybrid_command(name='queue', aliases=['q'], description='Shows the current song queue.')
    @app_commands.guild_only()
    async def _queue(self, ctx: Context):
        player: Player | None = ctx.voice_client
        if player is None:
            raise NoPlayerError('Bot is not in voice channel.')
        if not player.is_connected():
            raise PlayerNotConnectedError('Bot is not connected.')

        if len(player.queue) < 1:
            await ctx.reply('The queue is empty. Add some songs to view the queue.')
            return await ctx.log('Queue is empty.')

        entries: list[wavelink.YouTubeTrack] = list(player.queue)  # type: ignore # nopep8
        await Paginator(QueueSource(entries, ctx.author)).start(ctx)

    @commands.hybrid_command(name='loop', aliases=['l'], description='Changes the loop mode to the given mode.')
    @app_commands.guild_only()
    @app_commands.describe(mode='The mode to change the loop mode to. Can be `Song`, `Queue`, or `None`. Changes to next mode if omitted.')
    async def _loop(self, ctx: Context, mode: Literal['Song', 'Queue', 'None'] | None = None):
        player: Player | None = ctx.voice_client
        if player is None:
            raise NoPlayerError('Bot is not in voice channel.')
        if not player.is_connected():
            raise PlayerNotConnectedError('Bot is not connected.')

        if mode in ('Song', 'Queue'):
            player.loop_mode = mode
        elif mode == 'None':
            player.loop_mode = None
        else:
            if player.loop_mode is None:
                player.loop_mode = 'Song'
            elif player.loop_mode == 'Song':
                player.loop_mode = 'Queue'
            else:
                player.loop_mode = None
        await ctx.reply(f'Loop mode set to `{player.loop_mode}`.')

    @commands.hybrid_command(name='remove', aliases=['rm'], description='Removes a song from the queue.')
    @app_commands.guild_only()
    @app_commands.describe(index='The index of the song that should be removed from the queue (first song = 1).')
    async def _remove(self, ctx: Context, index: int):
        player: Player | None = ctx.voice_client
        if player is None:
            raise NoPlayerError('Bot is not in voice channel.')
        if not player.is_connected():
            raise PlayerNotConnectedError('Bot is not connected.')

        if len(player.queue) < 1:
            await ctx.reply('The queue is empty.')
            return await ctx.log('Queue is empty.')

        del player.queue[index - 1]

        await ctx.reply(f'Removed track from the queue.')

    @commands.hybrid_command(name='pause', aliases=['pau', 'pa'], description='Pauses the current song.')
    @app_commands.guild_only()
    async def _pause(self, ctx: Context):
        player: Player | None = ctx.voice_client
        if player is None:
            raise NoPlayerError('Bot is not in voice channel.')
        if not player.is_connected():
            raise PlayerNotConnectedError('Bot is not connected.')
        if player.is_paused():
            await ctx.reply('The player is already paused.')
            return await ctx.log('Player is already paused.')

        if self.is_privileged(ctx):
            await ctx.reply('The player was paused.')
            await player.set_pause(True)
            return
        else:
            await ctx.reply('Only the original requester may pause the player.')
            return await ctx.log('Not privileged to pause.')

    @commands.hybrid_command(name='resume', aliases=['res', 'r'], description='Resume the current song.')
    @app_commands.guild_only()
    async def _resume(self, ctx: Context):
        player: Player | None = ctx.voice_client
        if player is None:
            raise NoPlayerError('Bot is not in voice channel.')
        if not player.is_connected():
            raise PlayerNotConnectedError('Bot is not connected.')
        if not player.is_paused():
            await ctx.send('The player is not paused.')
            return await ctx.log('Player is not paused.')

        if self.is_privileged(ctx):
            await ctx.reply('The player was resumed.')
            await player.set_pause(False)
            return
        else:
            await ctx.reply(f'Only the original requester may resume the player.')
            return await ctx.log('Not privileged to resume.')

    @commands.hybrid_command(name='skip', aliases=['s', 'next'], description='Skips the currently playing song.')
    @app_commands.guild_only()
    @app_commands.describe(to='The index of the song that should be skipped to. DEFAULT: 1')
    async def _skip(self, ctx: Context, to: int = 1):
        player: Player | None = ctx.voice_client
        if player is None:
            raise NoPlayerError('Bot is not in voice channel.')
        if not player.is_connected():
            raise PlayerNotConnectedError('Bot is not connected.')

        if self.is_privileged(ctx):
            if to > 1:
                if len(player.queue) < to:
                    await ctx.reply('The queue is not long enough to skip to that index.')
                    return await ctx.log('Queue is not long enough to skip to that index.')
                for _ in range(to - 1):
                    del player.queue[0]
                if len(player.queue) > 0:
                    await ctx.reply(f'Skipped to **{player.queue[0].title}**.')  # type: ignore # nopep8
                else:
                    await ctx.reply('Skipped to the end of the queue.')
            elif to < 1:
                await ctx.reply('The index must be >= 1.')
                return await ctx.log('Index must be >= 1.')
            else:
                await ctx.reply(f'Skipped{" **" + player.source.title + "**" if isinstance(player.source, wavelink.YouTubeTrack) else ""}.')
            await player.stop()
            return
        else:
            await ctx.reply(f'Only the original requester may skip a song.')
            return await ctx.log('Not privileged to skip.')

    @commands.hybrid_command(name='shuffle', aliases=['mix', 'shuf'], description='Shuffles the queue.')
    @app_commands.guild_only()
    async def _shuffle(self, ctx: Context):
        player: Player | None = ctx.voice_client
        if player is None:
            raise NoPlayerError('Bot is not in voice channel.')
        if not player.is_connected():
            raise PlayerNotConnectedError('Bot is not connected.')

        if self.is_privileged(ctx):
            if len(player.queue) < 1:
                await ctx.reply('The queue is empty. Add some songs to shuffle the queue.')
                return await ctx.log('Queue is empty.')
            await ctx.reply('The queue was shuffled.')

            return random.shuffle(player.queue._queue)
        else:
            await ctx.reply(f'Only the original requester may shuffle the queue.', delete_after=15)
            return await ctx.log('Not privileged to shuffle.')

    @commands.hybrid_command(name='volume', aliases=['v', 'vol'], description='Changes the players volume.')
    @app_commands.guild_only()
    @app_commands.describe(volume='The amount you want to set the volume to.')
    async def _volume(self, ctx: Context, *, volume: float | None = None):
        player: Player | None = ctx.voice_client
        if player is None:
            raise NoPlayerError('Bot is not in voice channel.')
        if not player.is_connected():
            raise PlayerNotConnectedError('Bot is not connected.')

        if volume is None:
            return await ctx.reply(f'The volume is currently set to **{player.volume}%**.')

        if not self.is_privileged(ctx):
            await ctx.reply('Only the original requester may change the volume.')
            return await ctx.log('Not privileged to change the volume.')

        vol = int(volume)
        if vol < 0:
            vol = 0
        elif vol > 100:
            vol = 100

        await player.set_volume(vol)
        await ctx.reply(f'Set the volume to **{vol}**%')

    @commands.hybrid_command(name='seek', aliases=['sk'], description='Changes the players position in the song.')
    @app_commands.guild_only()
    @app_commands.describe(time='The time you want to seek to.')
    async def _seek(self, ctx: Context, *, time: Annotated[int | None, SeekTime]):
        player: Player | None = ctx.voice_client
        if player is None:
            raise NoPlayerError('Bot is not in voice channel.')
        if not player.is_connected():
            raise PlayerNotConnectedError('Bot is not connected.')

        if time is None:
            await ctx.reply('The provided time is invalid.')
            return await ctx.log('Invalid time provided.')

        if not self.is_privileged(ctx):
            await ctx.reply(f'Only the original requester may seek in the song.')
            return await ctx.log('Not privileged to seek.')

        await player.seek(time * 1000)
        await ctx.reply(f'Set the position to **{convert_seconds(time)}**.')


async def setup(bot: Advinas):
    await bot.add_cog(Music(bot))
