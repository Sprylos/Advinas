from __future__ import annotations

# std
from typing import Any, Callable, Coroutine

# packages
import aiohttp
import discord
import wavelink
import traceback
import infinitode
from discord.ext import commands, tasks
from motor.motor_asyncio import AsyncIOMotorClient

# local
import config
from common import custom, errors
from common.utils import codeblock

# exts to load
exts = [
    "account",
    "admin",
    "contest",
    "database",
    "inf",
    "misc",
    "music",
    "stats",
    "tags",
]
if not config.testing:
    exts.append("mod")


class Advinas(commands.Bot):
    def __init__(self, prefix: str) -> None:
        activity = discord.Activity(
            type=discord.ActivityType.watching, name="You | /invite | v4.4"
        )
        allowed_mentions = discord.AllowedMentions(
            everyone=False, users=True, roles=False, replied_user=False
        )
        intents = (
            "guilds",
            "members",
            "moderation",
            "voice_states",
            "presences",
            "messages",
            "reactions",
            "message_content",
        )
        super().__init__(
            command_prefix=commands.when_mentioned_or(prefix),
            activity=activity,
            allowed_mentions=allowed_mentions,
            help_command=None,
            case_insensitive=True,
            intents=discord.Intents(**{intent: True for intent in intents}),
        )

    async def start(self, token: str, *, reconnect: bool = True):
        # this is simply to make sure the session gets closed after the bot shuts down
        async with aiohttp.ClientSession(loop=self.loop) as self.session:
            async with infinitode.Session(session=self.session) as self.API:  # epic
                await super().start(token, reconnect=reconnect)

    async def setup_hook(self):
        nodes = [
            wavelink.Node(
                uri=config.uri, session=self.session, password=config.password
            )
        ]
        await wavelink.Pool.connect(client=self, nodes=nodes, cache_capacity=100)

        for ext in exts:
            await self.load_extension(f"exts.{ext}")
        await self.load_extension("jishaku")  # jsk

        self.BOT_CHANNELS: list[int] = config.bot_channels
        self.LEVELS: list[str]
        self.DB = AsyncIOMotorClient(config.mongo).inf2
        self.online_since = discord.utils.utcnow()

    async def get_context(
        self, origin: discord.Message | discord.Interaction, *, cls: Any = None
    ):
        return await super().get_context(origin, cls=custom.Context)

    async def on_ready(self) -> None:
        self.loop.create_task(self.ready())

    async def ready(self):
        await self.wait_until_ready()
        self.log_channel = self.get_partial_messageable(config.log_channel)
        self.task_channel = self.get_partial_messageable(config.task_channel)
        self.trace_channel = self.get_partial_messageable(config.trace_channel)
        self.join_channel = self.get_partial_messageable(config.join_channel)
        self.contest_channel = self.get_partial_messageable(config.contest)
        print("online")

    async def task_completion(
        self,
        loop: tasks.Loop[Any],
        fields: dict[str, str] | None = None,
    ) -> None:
        em = discord.Embed(
            title=f"**{loop.coro.__name__}** completed", colour=discord.Color.green()
        )

        dt = "%d.%m.%Y %H:%M"
        em.add_field(name="Time", value=discord.utils.utcnow().strftime(dt))
        if loop.next_iteration is not None:
            em.add_field(name="Next", value=loop.next_iteration.strftime(dt))

        if fields is not None:
            for name, value in fields.items():
                em.add_field(name=name, value=value, inline=False)

        await self.task_channel.send(embed=em)

    async def task_error(
        self,
        loop: tasks.Loop[Any],
        err: BaseException,
    ) -> None:
        em = discord.Embed(
            title=f"**{loop.coro.__name__}** failed", colour=discord.Color.red()
        )

        dt = "%d.%m.%Y %H:%M"
        em.add_field(name="Time", value=discord.utils.utcnow().strftime(dt))
        if loop.next_iteration is not None:
            em.add_field(name="Next", value=loop.next_iteration.strftime(dt))

        fmt = "".join(traceback.format_exception(type(err), err, err.__traceback__))
        tb = f"Error occured in task {loop.coro.__name__}\n" + fmt

        if len(tb) > 1990:
            await self.trace_channel.send(codeblock(tb[:1990]))
            await self.trace_channel.send(codeblock(tb[1990:]))
        elif len(tb) > 1000:
            await self.trace_channel.send(codeblock(tb))
        else:
            em.add_field(name="Traceback", value=codeblock(tb), inline=False)

        await self.trace_channel.send(embed=em)

    async def on_app_command_completion(
        self,
        inter: discord.Interaction,
        command: discord.app_commands.Command[Any, Any, Any] | discord.app_commands.ContextMenu,
    ) -> None:
        """Handles completed application commands."""
        if (
            command.__class__.__name__.startswith("Hybrid")
            or not inter.type is discord.InteractionType.application_command
        ):
            return

        if isinstance(command, discord.app_commands.Command):
            ctx = await self.get_context(inter)
            ctx.command_failed = inter.command_failed or ctx.command_failed
            return await ctx.log()

        command_name = f"{command.name} Context Menu"
        color = discord.Color.green()
        em = (
            discord.Embed(
                title=f"**{command_name}** used in `{inter.channel}`", colour=color
            )
            .set_footer(
                text=f"Command run by {inter.user}",
                icon_url=inter.user.display_avatar.url,
            )
            .add_field(name="**Success**", value="True")
            .add_field(
                name="**Channel**",
                value=f'`{inter.channel}` in `{inter.guild.name if inter.guild else "DM"}`',
            )
            .add_field(name="**Prefix**", value="`Context Menu`", inline=False)
            .add_field(name="**Command**", value=f"`{command_name}`")
        )
        await self.log_channel.send(embed=em)

    async def on_command_completion(self, ctx: custom.Context) -> None:
        """Handles completed commands."""
        await ctx.log()

    async def on_command_error(self, ctx: custom.Context, err: Exception) -> None:
        """Handles errored commands."""
        excs = (
            infinitode.errors.APIError,
            infinitode.errors.BadArgument,
            commands.BadArgument,
            commands.BadLiteralArgument,
            commands.MissingRequiredArgument,
            errors.TagError,
            commands.ExpectedClosingQuoteError,
            commands.UnexpectedQuoteError,
            discord.ClientException,
            commands.TooManyArguments,
            commands.CheckFailure,
            ValueError,
            wavelink.WavelinkException,
        )

        if isinstance(
            err,
            (
                commands.CommandInvokeError,
                commands.HybridCommandError,
                commands.ConversionError,
            ),
        ):
            err = err.original

        if isinstance(err, discord.app_commands.CommandInvokeError):
            err = err.original

        if isinstance(
            err,
            (commands.CommandNotFound, commands.NotOwner, commands.PrivateMessageOnly),
        ):
            return  # Ignore
        elif isinstance(err, errors.BadChannel):
            await ctx.log("Used in wrong channel.")
            await ctx.send(
                "Use commands in <#616583511826104355>.", delete_after=3, ephemeral=True
            )
            return
        elif isinstance(err, errors.BadLevel | errors.InCommandError):
            content = err.args[0]
            await ctx.log(getattr(err, "log", content))
        elif isinstance(err, excs):
            content = str(err)
            await ctx.log(content)
        else:
            await ctx.trace(err)
            content = "Something went really wrong and the issue has been reported. Please try again later."

        if isinstance(err, wavelink.LavalinkLoadException):
            content = "Failed to load tracks: " + err.error
        await ctx.reply(content)


if __name__ == "__main__":
    bot = Advinas(config.prefix)
    bot.run(config.token)
