import discord
import pomice
import asyncio
import random

from discord.ext import commands
from contextlib import suppress

from bot import Advinas
from common.utils import BadChannel, answer
from config import host, port, password


class Player(pomice.Player):
    """Custom pomice Player class."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.queue = asyncio.Queue()
        self.controller: discord.Message = None
        self.context: commands.Context = None
        self.dj: discord.Member = None

    async def do_next(self) -> None:
        if self.controller:
            with suppress(discord.HTTPException):
                await self.controller.delete()

        try:
            track: pomice.Track = self.queue.get_nowait()
        except asyncio.queues.QueueEmpty:
            return  # await self.teardown()

        await self.play(track)

        if track.is_stream:
            description = f":red_circle: **LIVE** [{track.title}]({track.uri}) [{track.requester.mention}]"
        else:
            description = f"[{track.title}]({track.uri}) [{track.requester.mention}]"
        embed = discord.Embed(title=f"Now playing", description=description)
        embed.set_thumbnail(url=track.thumbnail)
        self.controller = await self.context.send(embed=embed)

    async def teardown(self):
        with suppress((discord.HTTPException), (KeyError)):
            await self.destroy()
            if self.controller:
                await self.controller.delete()

    def set_context(self, ctx: commands.Context):
        """Set context for the player"""
        self.context = ctx
        self.dj = ctx.author


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
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

    def is_privileged(self, ctx: commands.Context):
        player: Player = ctx.voice_client

        return player.dj == ctx.author or ctx.author.guild_permissions.kick_members

    async def cog_check(self, ctx) -> bool:
        if ctx.guild and ctx.guild.id == 590288287864848387:
            if ctx.channel.id not in (*self.bot.BOT_CHANNELS, 666369102981496832):
                raise BadChannel('Command not used in an allowed channel.')
        return True

    @commands.Cog.listener()
    async def on_pomice_track_end(self, player: Player, track, _):
        await player.do_next()

    @commands.Cog.listener()
    async def on_pomice_track_stuck(self, player: Player, track, _):
        await player.do_next()

    @commands.Cog.listener()
    async def on_pomice_track_exception(self, player: Player, track, _):
        await player.do_next()

    @commands.command(aliases=['joi', 'j', 'summon', 'su', 'con', 'connect'])
    async def join(self, ctx: commands.Context, *, channel: discord.VoiceChannel = None) -> None:
        if not channel:
            channel = getattr(ctx.author.voice, "channel", None)
            if not channel:
                return await answer(ctx, content="You must be in a voice channel in order to use this command!")

        await ctx.author.voice.channel.connect(cls=Player)
        player: Player = ctx.voice_client
        player.set_context(ctx=ctx)
        await answer(ctx, content=f"Joined the voice channel `{channel.name}`")

    @commands.command(aliases=['disconnect', 'dc', 'disc', 'lv'])
    async def leave(self, ctx: commands.Context):
        if not (player := ctx.voice_client):
            return await answer(ctx, content="The bot is not in a voice channel.")

        await player.destroy()
        await answer(ctx, content="Player has left the channel.")

    @commands.command(aliases=['pla', 'p'])
    async def play(self, ctx: commands.Context, *, search: str) -> None:
        if not (player := ctx.voice_client):
            await ctx.invoke(self.join)
            player: Player = ctx.voice_client

        results = await player.get_tracks(search, ctx=ctx)

        if not results:
            return await answer(ctx, content="No results were found for that search term.")

        if isinstance(results, pomice.Playlist):
            for track in results.tracks:
                await player.queue.put(track)
        else:
            track = results[0]
            await player.queue.put(track)

        if not player.is_playing:
            await player.do_next()
        else:
            await answer(ctx, content=f'Queued **{track.title}**.')

    @commands.command(aliases=['np', 'now', 'playing'])
    async def nowplaying(self, ctx: commands.Context):
        if not (player := ctx.voice_client):
            return await answer(ctx, content="The bot is not in a voice channel.")
        if not player.is_connected:
            return
        track = player.current
        if track.is_stream:
            description = f":red_circle: **LIVE** [{track.title}]({track.uri}) [{track.requester.mention}]"
        else:
            description = f"[{track.title}]({track.uri}) [{track.requester.mention}]"
        embed = discord.Embed(title=f"Now playing", description=description)
        embed.set_thumbnail(url=track.thumbnail)
        await ctx.send(embed=embed)

    @commands.command(aliases=['q'])
    async def queue(self, ctx: commands.Context):
        if not (player := ctx.voice_client):
            return await answer(ctx, content="The bot is not in a voice channel.")

        if not player.is_connected:
            return
        if player.queue.qsize() < 1:
            return await answer(ctx, content='The queue is empty. Add some songs to view the queue.')
        songs = str()
        for c, track in enumerate(player.queue._queue):
            songs += f'{c+1}. [{track.title}]({track.uri}) [{track.requester.mention}]\n'
            if c == 14:
                songs += '...\n'
                break
        embed = discord.Embed(title='Queue', description=songs[:-1])
        await answer(ctx, embed=embed)

    @commands.command(aliases=['pau', 'pa'])
    async def pause(self, ctx: commands.Context):
        """Pause the currently playing song."""
        if not (player := ctx.voice_client):
            return await answer(ctx, content="The bot is not in a voice channel.")

        if player.is_paused or not player.is_connected:
            return

        if self.is_privileged(ctx):
            await answer(ctx, content='The player was paused.')
            return await player.set_pause(True)
        else:
            await answer(ctx, content='Only the original requester may pause the player.', delete_after=15)

    @commands.command(aliases=['res', 'r'])
    async def resume(self, ctx: commands.Context):
        """Resume a currently paused player."""
        if not (player := ctx.voice_client):
            return await answer(ctx, content="The bot is not in a voice channel.")

        if not player.is_paused or not player.is_connected:
            return

        if self.is_privileged(ctx):
            await answer(ctx, content='The player was resumed.')
            return await player.set_pause(False)
        else:
            await answer(ctx, content=f'Only the original requester may resume the player.', delete_after=15)

    @commands.command(aliases=['s', 'n', 'nex', 'next', 'sk'])
    async def skip(self, ctx: commands.Context):
        """Skip the currently playing song."""
        if not (player := ctx.voice_client):
            return await answer(ctx, content="The bot is not in a voice channel.")

        if not player.is_connected:
            return

        if ctx.author == player.current.requester or self.is_privileged(ctx):
            await answer(ctx, content='The song was skipped.')
            return await player.stop()
        else:
            await answer(ctx, content=f'Only the song requester or the original requester may skip a song.', delete_after=15)

    @commands.command()
    async def stop(self, ctx: commands.Context):
        """Stop the player and clear all internal states."""
        if not (player := ctx.voice_client):
            return await answer(ctx, content="The bot is not in a voice channel.")

        if not player.is_connected:
            return

        if self.is_privileged(ctx):
            await answer(ctx, content='The player was stopped.')
            return await player.teardown()
        else:
            await answer(ctx, content=f'Only the original requester may stop the player.', delete_after=15)

    @commands.command(aliases=['mix', 'shuf'])
    async def shuffle(self, ctx: commands.Context):
        """Shuffle the players queue."""
        if not (player := ctx.voice_client):
            return await answer(ctx, content="The bot is not in a voice channel.")

        if not player.is_connected:
            return

        if self.is_privileged(ctx):
            if player.queue.qsize() < 3:
                return await answer(ctx, content='The queue is empty. Add some songs to shuffle the queue.')
            await answer(ctx, content='The queue was shuffled.')
            player: Player
            return random.shuffle(player.queue._queue)
        else:
            await answer(ctx, content=f'Only the original requester may shuffle the queue.', delete_after=15)

    @commands.command(aliases=['v', 'vol'])
    async def volume(self, ctx: commands.Context, *, vol: int):
        """Change the players volume, between 1 and 100."""
        if not (player := ctx.voice_client):
            return await answer(ctx, content="The bot is not in a voice channel.")

        if not player.is_connected:
            return

        if not self.is_privileged(ctx):
            return await answer(ctx, content='Only the original requester may change the volume.')

        if not 0 < vol < 101:
            return await answer(ctx, content='Please enter a value between 1 and 100.')

        await player.set_volume(vol)
        await answer(ctx, content=f'Set the volume to **{vol}**%')


async def setup(bot: Advinas):
    await bot.add_cog(Music(bot))
