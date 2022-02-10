from aiohttp import ClientSession
from slash_util import Bot
from discord import Activity, ActivityType, Intents
from discord.ext.commands.errors import NotOwner
from discord.utils import utcnow
from pymongo import MongoClient
from discord.ext.commands import (
    CommandNotFound,
    CommandInvokeError,
    MissingRequiredArgument,
    when_mentioned_or
)
from common.api import APIData, APIError
from common.utils import (
    BadChannel,
    BadLevel,
    answer,
    load_json,
    log,
    trace
)


# exts to load
exts = (
    'admin',
    'database',
    'inf',
    'misc',
    'mod'
)

config = load_json("data/config.json")


class Advinas(Bot):
    def __init__(self, prefix: str = None) -> None:
        super().__init__(command_prefix=when_mentioned_or(prefix or 'a!'), activity=Activity(type=ActivityType.watching, name="You | /invite | v2.1"),
                         help_command=None, case_insensitive=True, intents=Intents.all())

        # load extensions
        for ext in exts:
            self.load_extension(f'exts.{ext}')

    async def start(self, *args, **kwargs):
        # this is simply to make sure the session gets closed after the bot shuts down
        async with ClientSession(loop=self.loop) as self.SESSION:
            await super().start(*args, **kwargs)

    async def on_ready(self) -> None:
        self.BOT_CHANNELS: list[int] = config["bot_channels"]
        self.API = APIData(session=self.SESSION)
        # Switching to new DB soon ??
        self.DB = MongoClient(config['mongo']).inf2
        self.online_since = utcnow()
        self.loop.create_task(self.ready())

    async def ready(self):
        await self.wait_until_ready()
        self._log = await self.fetch_channel(config["log_channel"])
        self._trace = await self.fetch_channel(config["trace_channel"])
        print("online")

    async def on_command_error(self, ctx, err: Exception) -> None:
        '''Error handler'''

        if isinstance(err, CommandInvokeError):
            err = err.original

        if isinstance(err, CommandNotFound) or isinstance(err, NotOwner):
            return  # Ignore
        elif isinstance(err, BadChannel):
            await log(ctx, success=False, reason='Used in wrong channel.')
            try:
                return await ctx.send('Use commands in <#616583511826104355>.', ephemeral=True)
            except:
                return await ctx.reply('Use commands in <#616583511826104355>.', delete_after=3)
        elif isinstance(err, BadLevel):
            await log(ctx, success=False, reason='Invalid Level provided.')
            content = 'The provided level is invalid.'
        elif isinstance(err, APIError):
            await log(ctx, success=False, reason=err)
            content = err
        elif isinstance(err, MissingRequiredArgument):
            await log(ctx, success=False, reason='A required argument is missing.')
            content = 'A required argument is missing.'
        else:
            await trace(ctx, err=err)
            content = 'Something went really wrong and the issue has been reported. Please try again later.'
        return await answer(ctx, content=content)


if __name__ == '__main__':
    bot = Advinas()
    bot.run(config["token"])
