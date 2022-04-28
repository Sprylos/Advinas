# std
import asyncio
import random
from typing import(
    Optional,
)


# packages
import pomice
import discord
from discord import app_commands
from discord.ext import commands
from contextlib import suppress

# local
from bot import Advinas
from common.custom import BadChannel, Context
from config import host, port, password


class Player(pomice.Player):
    """Custom pomice Player class."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.queue = asyncio.Queue()
        self.controller: discord.Message
        self.context: commands.Context
        self.dj: discord.Member

    async def do_next(self) -> None:
        if self.controller:
            with suppress(discord.HTTPException):
                await self.controller.delete()

        try:
            track: pomice.Track = self.queue.get_nowait()
        except asyncio.queues.QueueEmpty:
            return  # await self.teardown()

        await self.play(track)

        requester = track.requester
        mention = requester.mention if requester else '@Invalid User'
        if track.is_stream:
            description = f":red_circle: **LIVE** [{track.title}]({track.uri}) [{mention}]"
        else:
            description = f"[{track.title}]({track.uri}) [{mention}]"
        embed = discord.Embed(title=f"Now playing", description=description)
        embed.set_thumbnail(url=track.thumbnail)
        self.controller = await self.context.send(embed=embed)

    async def teardown(self):
        with suppress((discord.HTTPException), (KeyError)):
            await self.destroy()
            if self.controller:
                await self.controller.delete()

    def set_context(self, ctx: Context):
        self.context = ctx
        # always in guild
        self.dj = ctx.author  # type: ignore


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
        player: Player = ctx.voice_client  # type: ignore
        # always in guild
        return player.dj == ctx.author or ctx.author.guild_permissions.kick_members  # type: ignore

    async def cog_check(self, ctx) -> bool:
        if ctx.guild and ctx.guild.id == 590288287864848387:
            if ctx.channel.id not in (*self.bot.BOT_CHANNELS, 666369102981496832):
                raise BadChannel('Command not used in an allowed channel.')
        return not not ctx.guild  # True if used in a guild

    @commands.Cog.listener()
    async def on_pomice_track_end(self, player: Player, track, _):
        await player.do_next()

    @commands.Cog.listener()
    async def on_pomice_track_stuck(self, player: Player, track, _):
        await player.do_next()

    @commands.Cog.listener()
    async def on_pomice_track_exception(self, player: Player, track, _):
        await player.do_next()

    @commands.hybrid_command(name='join', aliases=['j', 'summon', 'con', 'connect'], description='Makes the bot join your or the given voice channel.')
    @app_commands.guild_only()
    @app_commands.describe(channel='The channel you want the bot to join. Defaults to the channel you are in.')
    async def _join(self, ctx: Context, *, channel: Optional[discord.VoiceChannel] = None):
        if not channel:
            channel = getattr(ctx.author.voice, 'channel', None)  # type: ignore # nopep8
            if not channel:
                await ctx.reply('You must be in a voice channel in order to use this command!')
                return await ctx.log('Member not in a voice channel.')

        await channel.connect(cls=Player)
        player: Player = ctx.voice_client  # type: ignore
        player.set_context(ctx)
        await ctx.reply(f'Joined the voice channel `{channel.name}`.')
        await ctx.log()

    @commands.hybrid_command(name='leave', aliases=['disconnect', 'dc', 'disc', 'lv'], description='Makes the bot leave its current voice channel.')
    @app_commands.guild_only()
    async def _leave(self, ctx: Context):
        player: Player = ctx.voice_client  # type: ignore
        if not player:
            await ctx.reply('The bot is not in a voice channel.')
            return await ctx.log('Bot is not in a voice channel.')

        await player.destroy()
        await ctx.reply("Player has left the channel.")
        await ctx.log()

    @commands.hybrid_command(name='play', aliases=['pla', 'p'], description='Plays or queues the given song/songs.')
    @app_commands.guild_only()
    @app_commands.describe(search='The song/songs to play, can be a keyword to search or a direct link.')
    async def play(self, ctx: Context, *, search: str):
        player: Player = ctx.voice_client  # type: ignore
        if not player:
            await ctx.invoke(self._join)
            player: Player = ctx.voice_client  # type: ignore

        results = await player.get_tracks(search, ctx=ctx)

        if not results:
            await ctx.reply('No results were found for that search term.')
            return await ctx.log('No results found for query.')

        if isinstance(results, pomice.Playlist):
            queued = results.tracks[0].title
            for track in results.tracks:
                await player.queue.put(track)
        else:
            track = results[0]
            queued = track.title
            await player.queue.put(track)

        if not player.is_playing:
            await player.do_next()
        else:
            await ctx.reply(f'Queued **{queued}**.')
        await ctx.log()

    @commands.hybrid_command(name='nowplaying', aliases=['np', 'now', 'playing'], description='Shows the currently playing song.')
    @app_commands.guild_only()
    async def _nowplaying(self, ctx: Context):
        player: Player = ctx.voice_client  # type: ignore
        if not player:
            await ctx.reply('The bot is not in a voice channel.')
            return await ctx.log('Bot is not in a voice channel.')
        if not player.is_connected:
            return await ctx.log('Player is not connected.')
        track = player.current
        mention = track.requester.mention  # type: ignore
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
        player: Player = ctx.voice_client  # type: ignore
        if not player:
            await ctx.reply('The bot is not in a voice channel.')
            return await ctx.log('Bot is not in a voice channel.')

        if not player.is_connected:
            return await ctx.log('Player is not connected.')

        if player.queue.qsize() < 1:
            await ctx.reply('The queue is empty. Add some songs to view the queue.')
            return await ctx.log('Queue is empty.')

        songs = str()
        for c, track in enumerate(player.queue._queue):  # type: ignore
            songs += f'{c+1}. [{track.title}]({track.uri}) [{track.requester.mention}]\n'
            if c == 14:
                songs += '...\n'
                break
        embed = discord.Embed(title='Queue', description=songs[:-1])
        await ctx.reply(embed=embed)
        await ctx.log()

    @commands.hybrid_command(name='pause', aliases=['pau', 'pa'], description='Pauses the current song.')
    @app_commands.guild_only()
    async def _pause(self, ctx: Context):
        player: Player = ctx.voice_client  # type: ignore
        if not player:
            await ctx.reply('The bot is not in a voice channel.')
            return await ctx.log('Bot is not in a voice channel.')

        if player.is_paused or not player.is_connected:
            return await ctx.log('Player is not playing or not connected.')

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
        player: Player = ctx.voice_client  # type: ignore
        if not player:
            await ctx.reply('The bot is not in a voice channel.')
            return await ctx.log('Bot is not in a voice channel.')

        if not player.is_paused or not player.is_connected:
            return await ctx.log('Player is playing or not connected.')

        if self.is_privileged(ctx):
            await ctx.reply('The player was resumed.')
            await player.set_pause(False)
            return await ctx.log()
        else:
            await ctx.reply(f'Only the original requester may resume the player.')
            return await ctx.log('Not privileged to resume.')

    @commands.hybrid_command(name='skip', aliases=['s', 'next', 'sk'], description='Skips the currently playing song.')
    @app_commands.guild_only()
    async def skip(self, ctx: Context):
        player: Player = ctx.voice_client  # type: ignore
        if not player:
            await ctx.reply('The bot is not in a voice channel.')
            return await ctx.log('Bot is not in a voice channel.')

        if not player.is_connected:
            return await ctx.log('Player is not connected.')

        if ctx.author == player.current.requester or self.is_privileged(ctx):
            await ctx.reply('The song was skipped.')
            await player.stop()
            return await ctx.log()
        else:
            await ctx.reply(f'Only the song requester or the original requester may skip a song.')
            return await ctx.log('Not privileged to skip.')

    @commands.hybrid_command(name='stop', description='Stops the player.')
    @app_commands.guild_only()
    async def _stop(self, ctx: Context):
        player: Player = ctx.voice_client  # type: ignore
        if not player:
            await ctx.reply('The bot is not in a voice channel.')
            return await ctx.log('Bot is not in a voice channel.')

        if not player.is_connected:
            return await ctx.log('Player is not connected.')

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
        player: Player = ctx.voice_client  # type: ignore
        if not player:
            await ctx.reply('The bot is not in a voice channel.')
            return await ctx.log('Bot is not in a voice channel.')

        if not player.is_connected:
            return await ctx.log('Player is not connected.')

        if self.is_privileged(ctx):
            if player.queue.qsize() < 3:
                return await ctx.reply('The queue is empty. Add some songs to shuffle the queue.')
            await ctx.reply('The queue was shuffled.')
            player: Player
            return random.shuffle(player.queue._queue)  # type: ignore
        else:
            await ctx.reply(f'Only the original requester may shuffle the queue.', delete_after=15)

    @commands.hybrid_command(name='volume', aliases=['v', 'vol'], description='Changes the players volume.')
    @app_commands.guild_only()
    @app_commands.describe(volume='The amount you want to set the volume to.')
    async def volume(self, ctx: Context, *, volume: float):
        player: Player = ctx.voice_client  # type: ignore
        if not player:
            await ctx.reply('The bot is not in a voice channel.')
            return await ctx.log('Bot is not in a voice channel.')

        if not player.is_connected:
            return await ctx.log('Player is not connected.')

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


async def setup(bot: Advinas):
    await bot.add_cog(Music(bot))
