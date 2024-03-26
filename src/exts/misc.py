from __future__ import annotations

# std
import re
import traceback
from typing import TYPE_CHECKING

# packages
import discord
from discord import app_commands
from discord.ext import commands

# local
from common import custom
from common.errors import InCommandError
from common.utils import create_choices
from common.views import Invite
from common.custom import codeblock, Context

if TYPE_CHECKING:
    from bot import Advinas


class Misc(commands.Cog):
    def __init__(self, bot: Advinas):
        super().__init__()
        self.bot: Advinas = bot
        self.wiki_keys: dict[str, str] = {}
        self.ISSUE_REGEX = re.compile(r"##(\d{1,7})\D")
        self.ISSUE_NAME_RE = re.compile(
            r"<title>(\d{7}): (.*) - Prineside issue tracker<\/title>"
        )
        self.WIKI_RE = re.compile(
            r"""<li(?: class="allpagesredirect")?><a href="\/wiki\/([A-Za-z0-9-()_.]+)" (?:class="mw-redirect" )?title="(?P<page>[A-Za-z0-9-(). ]+)">(?P=page)<\/a><\/li>"""
        )
        self.WIKI_ENTRY = re.compile(r"[A-Za-z0-9-()_.]+")
        bot.loop.create_task(self.ready())

    async def ready(self):
        await self.bot.wait_until_ready()
        await self.prepare_wiki()

    async def get_text_from_url(
        self, url: str, /, message: discord.Message | None = None
    ) -> str:
        try:
            async with self.bot.session.get(url, raise_for_status=True) as r:
                return await r.text()
        except Exception as err:
            tb = codeblock(
                f"Error occured while requesting {url}\n"
                + "".join(traceback.format_exception(type(err), err, err.__traceback__))
            )
            if len(tb) > 1990:
                await self.bot.trace_channel.send(codeblock(tb[3:1990]))
                await self.bot.trace_channel.send(codeblock(tb[1990:-3]))
            else:
                await self.bot.trace_channel.send(tb)
            if message is not None:
                em = discord.Embed(
                    title=f"Error occured in issue listener in `{message.channel}`",
                    colour=discord.Color.red(),
                )
                em.add_field(name="**Message**", value=f"`{message.content}`")
                await self.bot.trace_channel.send(embed=em)
            raise

    async def prepare_wiki(self):
        url = "https://infinitode-2.fandom.com/wiki/Special:AllPages"
        text = await self.get_text_from_url(url)
        self.wiki_keys.clear()
        for match in self.WIKI_RE.finditer(text):
            key = match.group(1)
            self.wiki_keys[key.lower()] = key

    def _convert_query(self, query: str) -> str:
        query = query.replace(" ", "_").lower()
        if query in [
            "overview",
            "0.1",
            "0.2",
            "0.3",
            "0.4",
            "1.1",
            "1.2",
            "1.3",
            "1.4",
            "1.5",
            "1.6",
            "1.7",
            "1.8",
            "1.b1",
            "2.1",
            "2.2",
            "2.3",
            "2.4",
            "2.5",
            "2.6",
            "2.7",
            "2.8",
            "2.b1",
            "3.1",
            "3.2",
            "3.3",
            "3.4",
            "3.5",
            "3.6",
            "3.7",
            "3.8",
            "3.b1",
            "4.1",
            "4.2",
            "4.3",
            "4.4",
            "4.5",
            "4.6",
            "4.7",
            "4.8",
            "4.b1",
            "5.1",
            "5.2",
            "5.3",
            "5.4",
            "5.5",
            "5.6",
            "5.7",
            "5.8",
            "5.b1",
            "5.b2",
            "6.1",
            "6.2",
            "6.3",
            "6.4",
            "rumble",
            "dev",
            "zecred",
            "dq1",
            "dq2",
            "dq3",
            "dq4",
            "dq5",
            "dq6",
            "dq7",
            "dq8",
            "dq9",
            "dq10",
            "dq11",
            "dq12",
        ]:
            query = "level_" + query
        elif query in [
            "laser",
            "minigun",
            "freezing",
            "flamethrower",
            "sniper",
            "tesla",
            "crusher",
            "multishot",
            "basic",
            "gauss",
            "venom",
            "cannon",
            "missile",
            "splash",
            "antiair",
            "blast",
        ]:
            query += "_(tower)"
        elif query in [
            "jet",
            "strong",
            "healer",
            "light",
            "toxic",
            "heli",
            "regular",
            "armored",
            "creep",
            "fast",
            "fighter",
            "icy",
        ]:
            query += "_(enemy)"
        elif query in ["stakey", "mobchain", "constructor", "metaphor", "broot"]:
            query += "_(boss)"
        elif query in [
            "smoke_bomb",
            "firestorm",
            "fireball",
            "windstorm",
            "magnet",
            "blizzard",
            "nuke",
            "loic",
            "bullet_wall",
            "thunder",
            "ball_lightning",
            "overload",
        ]:
            query += "_(ability)"

        if query in self.wiki_keys:
            return self.wiki_keys[query]
        raise InCommandError("Sorry, could not find article.")

    # wiki command
    @commands.hybrid_command(name="wiki", description="Posts a link to the wiki.")
    @app_commands.describe(query="The query to search the wiki for.")
    async def wiki(self, ctx: Context, *, query: str | None = None):
        if query is None:
            return await ctx.reply(
                "https://infinitode-2.fandom.com/wiki/Infinitode_2_Wiki"
            )

        query = self._convert_query(query)
        url = "https://infinitode-2.fandom.com/wiki/" + query

        await ctx.reply(url)

    @wiki.autocomplete("query")
    async def _wiki_autocomplete(
        self, inter: discord.Interaction, current: str
    ) -> list[app_commands.Choice]:
        current = current.replace(" ", "_").lower()
        return create_choices(
            [self.wiki_keys[t] for t in self.wiki_keys.keys() if current in t]
        )

    @commands.Cog.listener("on_message")
    async def _issue_listener(self, message: discord.Message):
        if message.author.bot:
            return

        # 'e' is so that ##0000021 matches but ##00000215 doesn't
        match = self.ISSUE_REGEX.search(message.content + "e")
        if match is None:
            return

        issue = match.groups()[0]
        url = "https://tracker.prineside.com/view.php?id="
        text = await self.get_text_from_url(url + issue, message)
        match = self.ISSUE_NAME_RE.search(text)
        if match is not None:
            issue, name = match.groups()
            content = f"Found issue `{issue}`: `{name}`\n{url}{int(issue)}"
            await message.reply(content)
        else:
            await message.reply("Could not find issue, sorry.")

    # @commands.hybrid_command(name='rtfm', aliases=['rtfd'], description='Shows the javadoc entry related to the query.')
    # @custom.check_channel(590290050051342346, 1012088788949942414)
    # async def rtfm(self, ctx: Context):
    #     pass

    # ping command
    @commands.hybrid_command(name="ping", description="Shows the bot's latency.")
    @custom.check_channel()
    async def ping(self, ctx: Context):
        await ctx.reply(f"Latency: {round(self.bot.latency * 1000)}ms.", ephemeral=True)

    # invite command
    @commands.hybrid_command(
        name="invite",
        description="Gives you a link to invite the bot to your own server.",
    )
    @custom.check_channel()
    async def invite(self, ctx: Context):
        em = discord.Embed(
            description=r"[Invite The Bot](https://discord.com/api/oauth2/authorize?client_id=824289599065030756&permissions=309238025280&scope=bot%20applications.commands)"
        ).set_footer(
            text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url
        )
        await ctx.reply(embed=em, view=Invite())

    # uptime command
    @commands.hybrid_command(
        name="uptime", description="Shows the bots uptime since the last reboot."
    )
    @custom.check_channel()
    async def uptime(self, ctx: Context):
        delta_uptime = discord.utils.utcnow() - self.bot.online_since
        hours, remainder = divmod(int(delta_uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        await ctx.reply(
            content=f"Time since last reboot: **{days}d, {hours}h, {minutes}m, {seconds}s.**"
        )


async def setup(bot: Advinas):
    await bot.add_cog(Misc(bot))
