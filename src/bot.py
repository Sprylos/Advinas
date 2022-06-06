from __future__ import annotations

# std
from typing import Any

# packages
import infinitode
from aiohttp import ClientSession
from discord import (
    app_commands,
    Activity,
    ActivityType,
    AllowedMentions,
    Message,
    Intents,
    Interaction
)
from discord.utils import utcnow
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pomice.exceptions import InvalidSpotifyClientAuthorization, TrackLoadError
from discord.ext.commands import (
    Bot,
    BadArgument,
    CommandNotFound,
    CommandInvokeError,
    ExpectedClosingQuoteError,
    UnexpectedQuoteError,
    HybridCommandError,
    MissingRequiredArgument,
    NotOwner,
    when_mentioned_or
)

# local
import config
from common.custom import (
    BadChannel,
    BadLevel,
    Context,
    NoPlayerError,
    PlayerNotConnectedError,
    TagError
)


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


class Advinas(Bot):
    def __init__(self, prefix: str) -> None:
        super().__init__(
            command_prefix=when_mentioned_or(prefix),
            activity=Activity(
                type=ActivityType.watching, name="You | /invite | v3.0"),
            allowed_mentions=AllowedMentions(
                everyone=False, users=True, roles=False, replied_user=False),
            help_command=None,
            case_insensitive=True,
            intents=Intents.all()
        )

    async def start(self, *args: Any, **kwargs: Any):
        # this is simply to make sure the session gets closed after the bot shuts down
        async with ClientSession(loop=self.loop) as self.SESSION:
            async with infinitode.Session(session=self.SESSION) as self.API:  # epic
                await super().start(*args, **kwargs)

    async def setup_hook(self):
        for ext in exts:
            await self.load_extension(f'exts.{ext}')
        self.BOT_CHANNELS: list[int] = config.bot_channels
        self.LEVELS: list[str]
        self.DB: AsyncIOMotorDatabase = AsyncIOMotorClient(config.mongo).inf2
        self.online_since = utcnow()

    async def get_context(self, origin: Message | Interaction, *, cls: Any = None):
        return await super().get_context(origin, cls=Context)

    async def on_ready(self) -> None:
        self.loop.create_task(self.ready())

    async def ready(self):
        await self.wait_until_ready()
        self._log = await self.fetch_channel(config.log_channel)
        self._trace = await self.fetch_channel(config.trace_channel)
        self._join = await self.fetch_channel(config.join_channel)
        print("online")

    async def on_command_error(self, ctx: Context, err: Exception) -> None:
        '''Error handler'''
        excs = (infinitode.errors.APIError, infinitode.errors.BadArgument, BadArgument, TrackLoadError,
                MissingRequiredArgument, TagError, ExpectedClosingQuoteError, UnexpectedQuoteError,)

        if isinstance(err, (CommandInvokeError, HybridCommandError)):
            err = err.original

        if isinstance(err, app_commands.CommandInvokeError):
            err = err.original

        if isinstance(err, (CommandNotFound, NotOwner)):
            return  # Ignore
        elif isinstance(err, BadChannel):
            await ctx.log('Used in wrong channel.')
            await ctx.send('Use commands in <#616583511826104355>.', delete_after=3, ephemeral=True)
            return
        elif isinstance(err, BadLevel):
            await ctx.log('Invalid Level provided.')
            content = 'The provided level is invalid.'
        elif isinstance(err, NoPlayerError):
            await ctx.log('Bot is not in a voice channel.')
            content = 'The bot is not in a voice channel.'
        elif isinstance(err, PlayerNotConnectedError):
            await ctx.log('Player is not connected.')
            content = 'The player is not connected.'
        elif isinstance(err, InvalidSpotifyClientAuthorization):
            await ctx.log('Spotify link provided.')
            content = 'Spotify links are not supported at the time, sorry.'
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
