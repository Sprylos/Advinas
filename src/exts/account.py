from __future__ import annotations

# std
import re
import time
import asyncio
import traceback
from typing import Any, Literal, overload, TYPE_CHECKING

# packages
import aiohttp
import discord
from discord.ext import commands
from discord import app_commands, Interaction
from infinitode import Player
from infinitode.errors import APIError, BadArgument

# local
from common.custom import Context, app_check_channel
from common.images import Images
from common.utils import codeblock, create_choices
from common.errors import (
    BadChannel,
    InCommandError,
    InvalidPlayerError,
    NoPlayerProvidedError,
)

if TYPE_CHECKING:
    from bot import Advinas


class Account(commands.Cog):
    def __init__(self, bot: Advinas) -> None:
        self.bot = bot
        self.mention_regex = re.compile(r"<@!?([0-9]+)>")
        self.images = Images()
        self.ctx_menu = app_commands.ContextMenu(
            name="profile",
            callback=self.profile_context_menu,
        )
        self.ctx_menu.on_error = self.profile_ctx_error
        self.bot.tree.add_command(self.ctx_menu)
        bot.loop.create_task(self.ready())

    async def ready(self) -> None:
        await self.bot.wait_until_ready()
        await asyncio.sleep(3)
        self.accounts = self.bot.DB.discordnames
        self.nicks = self.bot.DB.nicknames
        payload: list[dict[str, Any]] = await self.nicks.find({}, {"_id": 0}).to_list(
            None
        )
        self.PLAYERIDS = {next(iter(doc.values()))["key"] for doc in payload} | {
            next(iter(doc)) for doc in payload
        }

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    async def cog_check(self, ctx: Context) -> bool:
        if ctx.guild and ctx.guild.id == 590288287864848387:
            if ctx.channel.id not in self.bot.BOT_CHANNELS:
                raise BadChannel
        return True

    async def add_connection(self, playerid: str, user_id: int | str) -> None:
        await self.accounts.update_one(
            {playerid: {"$exists": True}},
            {"$set": {playerid: str(user_id)}},
            upsert=True,
        )

    async def add_nickname(self, player: Player) -> None:
        data = {
            player.playerid: {"name": player.nickname, "key": player.nickname.lower()}
        }
        await self.nicks.update_one(
            data,
            {"$set": data},
            upsert=True,
        )

    @overload
    async def find_connection(
        self, user_id: int | str, raw: Literal[False] = False
    ) -> str | None: ...

    @overload
    async def find_connection(
        self, user_id: int | str, raw: Literal[True] = True
    ) -> dict[str, str] | None: ...

    async def find_connection(
        self, user_id: int | str, raw: bool = False
    ) -> dict[str, str] | str | None:
        data: dict[str, str] | None = await self.accounts.find_one(
            {"$text": {"$search": str(user_id)}},
            {"_id": 0},
        )
        if data is None or raw:
            return data
        return next(iter(data))

    async def find_by_name(self, name: str) -> dict[str, str] | None:
        data: dict[str, str] | None = await self.nicks.find_one(
            {"$text": {"$search": name.lower()}},
            {"_id": 0},
        )
        return data

    async def remove_connection(self, user_id: int):
        await self.accounts.delete_one(
            {"$text": {"$search": str(user_id)}},
        )

    @commands.hybrid_group(
        name="account",
        aliases=["ac"],
        description="Allows to manage connections to your Infinitode 2 Account.",
    )
    async def account(self, ctx: Context):
        await self._view(ctx)

    @account.command(
        name="view",
        aliases=["show"],
        description="Shows the currently linked playerid.",
    )
    async def _view(self, ctx: Context):
        playerid: str | None = await self.find_connection(ctx.author.id)
        if playerid is None:
            raise InCommandError("You have not linked an account.")

        await ctx.reply(f"Your account is linked to the playerid `{playerid}`.")

    @account.command(
        name="link",
        aliases=["add"],
        description="Links your discord account to any Infinitode 2 account. Used for /profile.",
    )
    @app_commands.describe(
        playerid="The playerid to link your account to. Format must be U-XXXX-XXXX-XXXXXX."
    )
    async def _link(self, ctx: Context, playerid: str):
        await ctx.defer()
        await ctx.bot.API.player(playerid)

        await self.add_connection(playerid, ctx.author.id)
        await ctx.reply(f"Successfully linked your account to playerid `{playerid}`.")

    @account.command(
        name="unlink",
        aliases=["remove"],
        description="Unlinks the Infinitode 2 account from your discord account.",
    )
    async def _unlink(self, ctx: Context):
        playerid: str | None = await self.find_connection(ctx.author.id)
        if playerid is None:
            raise InCommandError("You have not linked an account.")
        await self.remove_connection(ctx.author.id)

        await ctx.reply(
            f"Successfully unlinked your account from playerid `{playerid}`."
        )

    async def _find_player(
        self,
        author: discord.Member | discord.User,
        playerid: str | None = None,
        *,
        context_menu: bool = False,
    ) -> Player:
        pl: dict[str, Any] | None = {}
        player: Player | None = None
        if playerid is None:  # no playerid was given
            pl = (
                await self.find_connection(author.id, True)
                or await self.find_by_name(author.display_name)
                or await self.find_by_name(author.name)
            )
            if (
                pl is not None
            ):  # the playerid was found in the database using info about the author
                player = await self.bot.API.player(playerid=next(iter(pl)))
                playerid = ""  # make typechecker happy
            else:
                raise (
                    NoPlayerProvidedError
                    if not context_menu
                    else NoPlayerProvidedError(
                        "Could not fetch profile for this member."
                    )
                )
        else:
            try:
                upper = playerid.upper()
                player = await self.bot.API.player(
                    playerid=upper if upper.startswith("U-") else "U-" + upper
                )
            except (APIError, BadArgument):
                pass  # The playerid is invalid, but we don't give up yet
        if player is None:  # still no luck
            pl = await self.find_by_name(playerid)
            if pl is None:
                match = self.mention_regex.search(playerid)
                new_id = match[0] if match else playerid
                pl = await self.find_connection(new_id, True)
                if pl is None:
                    member = discord.utils.get(self.bot.users, name=playerid)
                    if member:
                        pl = await self.find_connection(member.id, True)
                    if pl is None:
                        raise InvalidPlayerError
        if player is None:
            player = await self.bot.API.player(playerid=next(iter(pl)))
        return player

    async def _generate_player(self, user_id: int, player: Player) -> discord.File:
        try:
            r = await self.bot.session.get(player.avatar_link, raise_for_status=True)
        except aiohttp.ClientResponseError:
            avatar_bytes = None
        else:
            avatar_bytes = await r.read()

        await player.fetch_daily_quest(self.bot.API)
        await player.fetch_skill_point(self.bot.API)

        final_buffer = await self.bot.loop.run_in_executor(
            None, self.images.profile_gen, player, avatar_bytes, user_id
        )

        return discord.File(filename=f"{player.playerid}.png", fp=final_buffer)

    # Profile command
    @commands.hybrid_command(
        name="profile",
        aliases=["prof"],
        description="Shows your in game profile in an image (NO ENDLESS LEADERBOARD DUE TO API LIMITATIONS).",
    )
    @app_commands.describe(
        playerid="The playerid of the player you want to see the profile of."
    )
    async def profile(self, ctx: Context, playerid: str | None = None) -> None:
        await ctx.defer()
        start_time: float = time.perf_counter()

        player: Player = await self._find_player(ctx.author, playerid)
        await self.add_nickname(player)

        file = await self._generate_player(ctx.author.id, player)
        await ctx.reply(
            f"Finished in {time.perf_counter() - start_time:0.3f}s", file=file
        )

    @profile.autocomplete("playerid")
    async def playerid_autocomplete(
        self, inter: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        current = current.lower()
        return create_choices(
            {
                i
                for i in self.PLAYERIDS
                if i.lower().startswith(current) or current in i.lower()
            }
        )

    # Profile context menu
    @app_check_channel()
    async def profile_context_menu(
        self, inter: Interaction, member: discord.Member
    ) -> None:
        await inter.response.defer()
        start_time: float = time.perf_counter()

        player: Player = await self._find_player(member, context_menu=True)
        await self.add_nickname(player)

        file = await self._generate_player(member.id, player)
        await inter.followup.send(
            f"Finished in {time.perf_counter() - start_time:0.3f}s", file=file
        )

    async def profile_ctx_error(
        self, inter: Interaction, err: app_commands.AppCommandError
    ) -> None:
        err = getattr(err, "original", err)
        ephemeral = False
        if isinstance(err, BadChannel):
            ephemeral = True
            await inter.response.defer(ephemeral=True)
            content = "Use commands in <#616583511826104355>."
        elif isinstance(err, InCommandError):
            content = err.args[0]
        elif isinstance(err, (APIError, BadArgument)):
            content = str(err)
        else:
            content = "Something went really wrong and the issue has been reported. Please try again later."
            await self.bot.trace_channel.send(
                codeblock(
                    "".join(
                        traceback.format_exception(type(err), err, err.__traceback__)
                    )
                )
            )
        await inter.followup.send(content, ephemeral=ephemeral)

        color = discord.Color.red()
        em = (
            discord.Embed(
                title=f"**Profile Context Menu** used in `{inter.channel}`",
                colour=color,
            )
            .set_footer(
                text=f"Command run by {inter.user}",
                icon_url=inter.user.display_avatar.url,
            )
            .add_field(name="**Success**", value="False")
            .add_field(
                name="**Channel**",
                value=f'`{inter.channel}` in `{inter.guild.name if inter.guild else "DM"}`',
            )
            .add_field(name="**Prefix**", value="Context Menu", inline=False)
            .add_field(name="**Message**", value=f"`{content}`")
        )
        await self.bot.log_channel.send(embed=em)


async def setup(bot: Advinas):
    await bot.add_cog(Account(bot))
