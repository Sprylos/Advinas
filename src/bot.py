from __future__ import annotations

# std
from typing import Any

# packages
import wavelink
import aiohttp
import discord
import infinitode
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

# local
import config
from common import custom


# exts to load
exts = [
    'admin',
    'database',
    'inf',
    'misc',
    'music',
    'tags',
]
if not config.testing:
    exts.append('mod')


class Advinas(commands.Bot):
    def __init__(self, prefix: str) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned_or(prefix),
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="You | /invite | v3.1"),
            allowed_mentions=discord.AllowedMentions(
                everyone=False, users=True, roles=False, replied_user=False),
            help_command=None,
            case_insensitive=True,
            intents=discord.Intents.all()
        )

    async def start(self, token: str, *, reconnect: bool = True):
        # this is simply to make sure the session gets closed after the bot shuts down
        async with aiohttp.ClientSession(loop=self.loop) as self.SESSION:
            async with infinitode.Session(session=self.SESSION) as self.API:  # epic
                await super().start(token, reconnect=reconnect)

    async def setup_hook(self):
        for ext in exts:
            await self.load_extension(f'exts.{ext}')
        self.BOT_CHANNELS: list[int] = config.bot_channels
        self.LEVELS: list[str]
        self.DB: AsyncIOMotorDatabase = AsyncIOMotorClient(config.mongo).inf2
        self.online_since = discord.utils.utcnow()

    async def get_context(self, origin: discord.Message | discord.Interaction, *, cls: Any = None):
        return await super().get_context(origin, cls=custom.Context)

    async def on_ready(self) -> None:
        self.loop.create_task(self.ready())

    async def ready(self):
        await self.wait_until_ready()
        self._log = self.get_partial_messageable(config.log_channel)
        self._trace = self.get_partial_messageable(config.trace_channel)
        self._join = self.get_partial_messageable(config.join_channel)
        print("online")

    async def on_command_completion(self, ctx: custom.Context) -> None:
        """Handles completed commands."""
        await ctx.log()

    async def on_command_error(self, ctx: custom.Context, err: Exception) -> None:
        """Handles errored commands."""
        excs = (
            infinitode.errors.APIError, infinitode.errors.BadArgument, commands.BadArgument, commands.BadLiteralArgument,
            wavelink.LoadTrackError, commands.MissingRequiredArgument, custom.TagError, commands.ExpectedClosingQuoteError,
            commands.UnexpectedQuoteError,
        )

        if isinstance(err, (commands.CommandInvokeError, commands.HybridCommandError)):
            err = err.original

        if isinstance(err, discord.app_commands.CommandInvokeError):
            err = err.original

        if isinstance(err, (commands.CommandNotFound, commands.NotOwner)):
            return  # Ignore
        elif isinstance(err, custom.BadChannel):
            await ctx.log('Used in wrong channel.')
            await ctx.send('Use commands in <#616583511826104355>.', delete_after=3, ephemeral=True)
            return
        elif isinstance(err, custom.BadLevel):
            await ctx.log('Invalid Level provided.')
            content = 'The provided level is invalid.'
        elif isinstance(err, custom.NoPlayerError):
            await ctx.log('Bot is not in a voice channel.')
            content = 'The bot is not in a voice channel.'
        elif isinstance(err, custom.PlayerNotConnectedError):
            await ctx.log('Player is not connected.')
            content = 'The player is not connected.'
        elif isinstance(err, excs):
            await ctx.log(str(err))
            content = str(err)
        else:
            await ctx.trace(err)
            content = 'Something went really wrong and the issue has been reported. Please try again later.'
        await ctx.reply(content)


if __name__ == '__main__':
    bot = Advinas('a?' if config.testing else 'a!')

    from subprocess import Popen
    import time
    process = Popen(['java', '-jar', 'Lavalink.jar'])
    time.sleep(10)
    bot.run(config.token)
