from __future__ import annotations

# std
import re
import traceback
from typing import TYPE_CHECKING

# packages
import discord
from discord.ext import commands

# local
from common.views import Invite
from common.custom import codeblock, Context

if TYPE_CHECKING:
    from bot import Advinas


class Misc(commands.Cog):
    def __init__(self, bot: Advinas):
        super().__init__()
        self.bot: Advinas = bot
        bot.loop.create_task(self.ready())

    async def ready(self):
        await self.bot.wait_until_ready()
        self.ISSUE_REGEX = re.compile(r'##(\d{1,7})\D')
        self.ISSUE_NAME_RE = re.compile(
            r'<title>(\d{7}): (.*) - Prineside issue tracker<\/title>')

    @commands.Cog.listener('on_message')
    async def _issue_listener(self, message: discord.Message):
        if message.author.bot:
            return

        # 'e' is so that ##0000021 matches but ##00000215 doesn't
        match = self.ISSUE_REGEX.search(message.content + 'e')
        if match is None:
            return

        issue = match.groups()[0]
        url = 'https://tracker.prineside.com/view.php?id='
        try:
            async with self.bot.session.get(url + issue, raise_for_status=True) as r:
                match = self.ISSUE_NAME_RE.search(await r.text())
                if match is not None:
                    issue, name = match.groups()
                    content = f'Found issue `{issue}`: `{name}`\n{url}{int(issue)}'
                    await message.reply(content)
                else:
                    await message.reply('Could not find issue, sorry.')
        except Exception as err:
            tb = codeblock('Error occured in issue listener\n' + ''.join(
                traceback.format_exception(type(err), err, err.__traceback__)))
            if len(tb) > 1990:
                await self.bot._trace.send(codeblock(tb[3:1990]))
                await self.bot._trace.send(codeblock(tb[1990:-3]))
            else:
                await self.bot._trace.send(tb)
            em = discord.Embed(
                title=f"Error occured in issue listener in `{message.channel}`", colour=discord.Color.red())
            em.add_field(name='**Message**', value=f'`{message.content}`')
            await self.bot._trace.send(embed=em)

    def cog_check(self, ctx: Context) -> bool:
        if ctx.guild and ctx.guild.id == 590288287864848387:
            if ctx.channel.id not in self.bot.BOT_CHANNELS:
                raise BadChannel
        return True

    # ping command
    @commands.hybrid_command(name='ping', description='Shows the bot\'s latency.')
    async def ping(self, ctx: Context):
        await ctx.reply(f'Latency: {round(self.bot.latency * 1000)}ms.', ephemeral=True)

    # invite command

    @commands.hybrid_command(name='invite', description='Gives you a link to invite the bot to your own server.')
    async def invite(self, ctx: Context):
        em = discord.Embed(
            description=r'[Invite The Bot](https://discord.com/api/oauth2/authorize?client_id=824289599065030756&permissions=309238025280&scope=bot%20applications.commands)'
        ).set_footer(
            text=f'Requested by {ctx.author}', icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=em, view=Invite())

    # uptime command

    @commands.hybrid_command(name='uptime', description='Shows the bots uptime since the last reboot.')
    async def uptime(self, ctx: Context):
        delta_uptime = discord.utils.utcnow() - self.bot.online_since
        hours, remainder = divmod(int(delta_uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        await ctx.reply(content=f"Time since last reboot: **{days}d, {hours}h, {minutes}m, {seconds}s.**")


async def setup(bot: Advinas):
    await bot.add_cog(Misc(bot))
