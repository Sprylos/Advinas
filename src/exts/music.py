from __future__ import annotations

# std
import random
from typing import Annotated, Literal, TYPE_CHECKING

# packages
import pomice
import discord
from discord import app_commands, ClientException, VoiceChannel
from discord.ext import commands

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
)

if TYPE_CHECKING:
    from bot import Advinas


class Music(commands.Cog):
    def __init__(self, bot: Advinas) -> None:
        self.bot = bot
        self.pomice = pomice.NodePool()

        bot.loop.create_task(self.start_nodes())

    async def start_nodes(self):
        await self.bot.wait_until_ready()
        await self.pomice.create_node(
            bot=self.bot,
            host=host,
            port=port,
            password=password,
            identifier="MAIN"
        )

    def is_privileged(self, ctx: Context) -> bool:
        player: Player | None = ctx.voice_client
        # always in guild
        return player.dj == ctx.author or ctx.author.guild_permissions.kick_members  # type: ignore

    async def cog_check(self, ctx: Context) -> bool:
        if ctx.guild and ctx.guild.id == 590288287864848387:
            if ctx.channel.id not in (*self.bot.BOT_CHANNELS, 666369102981496832):
                raise BadChannel('Command not used in an allowed channel.')
        return not not ctx.guild  # True if used in a guild

    @commands.Cog.listener()
    async def on_pomice_track_end(self, player: Player, track: pomice.Track, _):
        if player.loop_mode == 'Song':
            player.queue.insert(0, track)
        await player.do_next()

    @commands.Cog.listener()
    async def on_pomice_track_stuck(self, player: Player, track: pomice.Track, _):
        await player.do_next()

    @commands.Cog.listener()
    async def on_pomice_track_exception(self, player: Player, track: pomice.Track, _):
        await player.do_next()

    @commands.hybrid_command(name='join', aliases=['j', 'summon', 'con', 'connect'], description='Makes the bot join your or the given voice channel.')
    @app_commands.guild_only()
    @app_commands.describe(channel='The channel you want the bot to join. Defaults to the channel you are in.')
    async def _join(self, ctx: Context, *, channel: discord.VoiceChannel | None = None):
        if not channel:
            channel = getattr(ctx.author.voice, 'channel', None)  # type: ignore # nopep8
            if not channel:
                await ctx.reply('You must be in a voice channel in order to use this command!')
                return await ctx.log('Member not in a voice channel.')

        try:
            await channel.connect(cls=Player)
        except ClientException as e:
            await ctx.reply(str(e))
            return await ctx.log(str(e))
        player: Player = ctx.voice_client  # type: ignore
        player.set_context(ctx)
        await ctx.reply(f'Joined the voice channel `{channel.name}`.')
        await ctx.log()

    @commands.hybrid_command(name='leave', aliases=['disconnect', 'dc', 'disc', 'lv'], description='Makes the bot leave its current voice channel.')
    @app_commands.guild_only()
    async def _leave(self, ctx: Context):
        player: Player | None = ctx.voice_client
        if not player:
            raise NoPlayerError('Bot is not connected.')
        await player.destroy()
        await ctx.reply("Player has left the channel.")
        await ctx.log()

    @commands.hybrid_command(name='play', aliases=['pla', 'p'], description='Plays or queues the given song/songs.')
    @app_commands.guild_only()
    @app_commands.describe(search='The song/songs to play, can be a keyword to search or a direct link.')
    async def _play(self, ctx: Context, *, search: str):
        player: Player | None = ctx.voice_client
        if not player:
            await ctx.invoke(self._join)
            player: Player | None = ctx.voice_client
            if not player:
                await ctx.reply('Failed to create player (try again).')
                return await ctx.log("Failed to create player.")

        results = await player.get_tracks(search, ctx=ctx)

        if not results:
            await ctx.reply('No results were found for that search term.')
            return await ctx.log('No results found for query.')

        if isinstance(results, pomice.Playlist):
            queued = results.name
            for track in results.tracks:
                player.queue.append(track)
        else:
            track = results[0]
            queued = track.title
            player.queue.append(track)

        if not player.is_playing:
            await player.do_next()
        else:
            await ctx.reply(f'Queued **{queued}**.')
        await ctx.log()

    @commands.hybrid_command(name='reconnect', aliases=['rc'], description='Reconnects to the channel while saving the current queue (In case the bot dies).')
    @app_commands.guild_only()
    async def _reconnect(self, ctx: Context):
        old_player: Player | None = ctx.voice_client
        if not old_player:
            raise NoPlayerError('Bot is not in voice channel.')
        if not old_player.is_connected:
            raise PlayerNotConnectedError('Bot is not connected.')

        channel: Optional[VoiceChannel] = getattr(ctx.author.voice, 'channel', None)  # type: ignore # nopep8
        if not channel:
            await ctx.reply('You must be in a voice channel in order to use this command!')
            return await ctx.log('Member not in a voice channel.')

        queue = [old_player.current]
        queue.extend(old_player.queue)
        await old_player.teardown()

        try:
            await channel.connect(cls=Player)
        except ClientException as e:
            await ctx.reply(str(e))
            return await ctx.log(str(e))

        player: Player | None = ctx.voice_client
        if not player:
            await ctx.reply('Failed to create player (try again).')
            return await ctx.log("Failed to create player.")
        player.set_context(ctx)
        player.queue.extend(queue)

        await player.do_next()
        await ctx.reply('Reconnected the bot.')
        await ctx.log()

    @commands.hybrid_command(name='nowplaying', aliases=['np', 'now', 'playing'], description='Shows the currently playing song.')
    @app_commands.guild_only()
    async def _nowplaying(self, ctx: Context):
        player: Player | None = ctx.voice_client
        if not player:
            raise NoPlayerError('Bot is not in voice channel.')
        if not player.is_connected:
            raise PlayerNotConnectedError('Bot is not connected.')
        track = player.current
        if not track:
            await ctx.reply('No track is currently playing.')
            return await ctx.log('No track is currently playing.')
        mention = track.requester.mention if track.requester else '@Invalid User'
        if track.is_stream:
            description = f":red_circle: **LIVE** [{track.title}]({track.uri}) [{mention}]"
        else:
            description = f"[{track.title}]({track.uri}) [{mention}]"
        embed = discord.Embed(title=f"Now playing", description=description)
        embed.set_thumbnail(url=track.thumbnail)
        await ctx.send(embed=embed)
        await ctx.log()

    @commands.hybrid_command(name='queue', aliases=['q'], description='Shows the current song queue.')
    @app_commands.guild_only()
    async def _queue(self, ctx: Context):
        player: Player | None = ctx.voice_client
        if not player:
            raise NoPlayerError('Bot is not in voice channel.')
        if not player.is_connected:
            raise PlayerNotConnectedError('Bot is not connected.')

        if len(player.queue) < 1:
            await ctx.reply('The queue is empty. Add some songs to view the queue.')
            return await ctx.log('Queue is empty.')

        await ctx.log()
        await Paginator(QueueSource(player.queue, ctx.author)).start(ctx)

    @commands.hybrid_command(name='loop', aliases=['l'], description='Changes the loop mode to the given mode.')
    @app_commands.guild_only()
    @app_commands.describe(mode='The mode to change the loop mode to. Can be `Song`, `Queue`, or `None`. Changes to next mode if omitted.')
    async def _loop(self, ctx: Context, mode: Literal['Song', 'Queue', 'None'] | None = None):
        player: Player | None = ctx.voice_client
        if not player:
            raise NoPlayerError('Bot is not in voice channel.')
        if not player.is_connected:
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
        await ctx.log()

    @commands.hybrid_command(name='remove', aliases=['rm'], description='Removes a song from the queue.')
    @app_commands.guild_only()
    @app_commands.describe(index='The index of the song that should be removed from the queue (first song = 1).')
    async def _remove(self, ctx: Context, index: int):
        player: Player | None = ctx.voice_client
        if not player:
            raise NoPlayerError('Bot is not in voice channel.')
        if not player.is_connected:
            raise PlayerNotConnectedError('Bot is not connected.')

        if len(player.queue) < 1:
            await ctx.reply('The queue is empty.')
            return await ctx.log('Queue is empty.')

        try:
            track = player.queue.pop(index - 1)
        except IndexError:
            await ctx.reply('No queue element found at that index.')
            return await ctx.log('No queue element at that index.')

        await ctx.reply(f'Removed **{track.title}** from the queue.')
        await ctx.log()

    @commands.hybrid_command(name='pause', aliases=['pau', 'pa'], description='Pauses the current song.')
    @app_commands.guild_only()
    async def _pause(self, ctx: Context):
        player: Player | None = ctx.voice_client
        if not player:
            raise NoPlayerError('Bot is not in voice channel.')
        if not player.is_connected:
            raise PlayerNotConnectedError('Bot is not connected.')
        if player.is_paused:
            await ctx.reply('The player is already paused.')
            return await ctx.log('Player is already paused.')

        if self.is_privileged(ctx):
            await ctx.reply('The player was paused.')
            await player.set_pause(True)
            return await ctx.log()
        else:
            await ctx.reply('Only the original requester may pause the player.')
            return await ctx.log('Not privileged to pause.')

    @commands.hybrid_command(name='resume', aliases=['res', 'r'], description='Resume the current song.')
    @app_commands.guild_only()
    async def _resume(self, ctx: Context):
        player: Player | None = ctx.voice_client
        if not player:
            raise NoPlayerError('Bot is not in voice channel.')
        if not player.is_connected:
            raise PlayerNotConnectedError('Bot is not connected.')
        if not player.is_paused:
            await ctx.send('The player is not paused.')
            return await ctx.log('Player is not paused.')

        if self.is_privileged(ctx):
            await ctx.reply('The player was resumed.')
            await player.set_pause(False)
            return await ctx.log()
        else:
            await ctx.reply(f'Only the original requester may resume the player.')
            return await ctx.log('Not privileged to resume.')

    @commands.hybrid_command(name='skip', aliases=['s', 'next'], description='Skips the currently playing song.')
    @app_commands.guild_only()
    @app_commands.describe(to='The index of the song that should be skipped to. DEFAULT: 1')
    async def _skip(self, ctx: Context, to: int = 1):
        player: Player | None = ctx.voice_client
        if not player:
            raise NoPlayerError('Bot is not in voice channel.')
        if not player.is_connected:
            raise PlayerNotConnectedError('Bot is not connected.')

        if ctx.author == player.current.requester or self.is_privileged(ctx):
            if to > 1:
                if len(player.queue) < to:
                    await ctx.reply('The queue is not long enough to skip to that index.')
                    return await ctx.log('Queue is not long enough to skip to that index.')
                del player.queue[:to - 1]
                if len(player.queue) > 0:
                    await ctx.reply(f'Skipped to **{player.queue[0].title}**.')
                else:
                    await ctx.reply('Skipped to the end of the queue.')
            elif to < 1:
                await ctx.reply('The index must be >= 1.')
                return await ctx.log('Index must be >= 1.')
            else:
                await ctx.reply(f'Skipped **{player.current.title}**.')
            await player.stop()
            return await ctx.log()
        else:
            await ctx.reply(f'Only the song requester or the original requester may skip a song.')
            return await ctx.log('Not privileged to skip.')

    @commands.hybrid_command(name='stop', description='Stops the player.')
    @app_commands.guild_only()
    async def _stop(self, ctx: Context):
        player: Player | None = ctx.voice_client
        if not player:
            raise NoPlayerError('Bot is not in voice channel.')
        if not player.is_connected:
            raise PlayerNotConnectedError('Bot is not connected.')

        if self.is_privileged(ctx):
            await ctx.reply('The player was stopped.')
            await player.teardown()
            return await ctx.log()
        else:
            await ctx.reply(f'Only the original requester may stop the player.')
            return await ctx.log('Not privileged to stop.')

    @commands.hybrid_command(name='shuffle', aliases=['mix', 'shuf'], description='Shuffles the queue.')
    @app_commands.guild_only()
    async def _shuffle(self, ctx: Context):
        player: Player | None = ctx.voice_client
        if not player:
            raise NoPlayerError('Bot is not in voice channel.')
        if not player.is_connected:
            raise PlayerNotConnectedError('Bot is not connected.')

        if self.is_privileged(ctx):
            if len(player.queue) < 1:
                await ctx.reply('The queue is empty. Add some songs to shuffle the queue.')
                return await ctx.log('Queue is empty.')
            await ctx.reply('The queue was shuffled.')
            await ctx.log()
            return random.shuffle(player.queue)
        else:
            await ctx.reply(f'Only the original requester may shuffle the queue.', delete_after=15)
            return await ctx.log('Not privileged to shuffle.')

    @commands.hybrid_command(name='volume', aliases=['v', 'vol'], description='Changes the players volume.')
    @app_commands.guild_only()
    @app_commands.describe(volume='The amount you want to set the volume to.')
    async def _volume(self, ctx: Context, *, volume: float):
        player: Player | None = ctx.voice_client
        if not player:
            raise NoPlayerError('Bot is not in voice channel.')
        if not player.is_connected:
            raise PlayerNotConnectedError('Bot is not connected.')

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
        await ctx.log()

    @commands.hybrid_command(name='seek', aliases=['sk'], description='Changes the players position in the song.')
    @app_commands.guild_only()
    @app_commands.describe(time='The time you want to seek to.')
    async def _seek(self, ctx: Context, *, time: Annotated[int, SeekTime]):
        player: Player | None = ctx.voice_client
        if not player:
            raise NoPlayerError('Bot is not in voice channel.')
        if not player.is_connected:
            raise PlayerNotConnectedError('Bot is not connected.')

        if not (ctx.author == player.current.requester or self.is_privileged(ctx)):
            await ctx.reply(f'Only the song requester or the original requester may seek in the song.')
            return await ctx.log('Not privileged to seek.')

        try:
            await player.seek(time * 1000)
        except pomice.TrackInvalidPosition:
            await ctx.reply('The provided time is invalid.')
            return await ctx.log('Invalid time provided.')
        await ctx.reply(f'Set the position to **{time}** seconds.')
        await ctx.log()


async def setup(bot: Advinas):
    await bot.add_cog(Music(bot))
