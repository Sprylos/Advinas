import discord
from discord.ext import commands
import slash_util
from bot import Advinas
from common.utils import BadChannel, answer
from discord.ext.commands import Context
from common.views import Invite
from typing import Union


class Misc(slash_util.Cog):
    def __init__(self, bot: Advinas):
        self.bot: Advinas
        super().__init__(bot)

    async def cog_check(self, ctx) -> bool:
        if ctx.guild and ctx.guild.id == 590288287864848387:
            if ctx.channel.id not in self.bot.BOT_CHANNELS:
                raise BadChannel('Command not used in an allowed channel.')
        return True

    async def slash_command_error(self, ctx, error: Exception) -> None:
        await self.bot.on_command_error(ctx, err=error)

    # ping command
    @slash_util.slash_command(name='ping')
    async def _ping(self, ctx: slash_util.Context):
        '''Shows the bot's latency.'''
        await ctx.send(f'Latency: {round(self.bot.latency * 1000)}ms.', ephemeral=True)

    @commands.command(name='ping')
    async def ping(self, ctx: Context):
        await ctx.reply(f'Latency: {round(self.bot.latency * 1000)}ms.', mention_author=False)

    # invite command
    @slash_util.slash_command(name='invite')
    async def _invite(self, ctx: slash_util.Context):
        '''Sends a link to invite the bot to your own server.'''
        await self.cog_check(ctx)
        await self.invite(ctx)

    @commands.command(name='invite')
    async def invite(self, ctx: Union[Context, slash_util.Context]):
        em = discord.Embed(
            description=r'[Invite The Bot](https://discord.com/api/oauth2/authorize?client_id=824289599065030756&permissions=309238025280&scope=bot%20applications.commands)'
        ).set_footer(
            text=f'Requested by {ctx.author}', icon_url=ctx.author.avatar.url)
        await answer(ctx, embed=em, view=Invite())

    # uptime command
    @slash_util.slash_command(name='uptime')
    async def _uptime(self, ctx: slash_util.Context):
        '''Shows the bot's uptime.'''
        await self.cog_check(ctx)
        await self.uptime(ctx)

    @commands.command(name='uptime')
    async def uptime(self, ctx: Union[Context, slash_util.Context]):
        delta_uptime = discord.utils.utcnow() - self.bot.online_since
        hours, remainder = divmod(int(delta_uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        await answer(ctx, content=f"Online for: **{days}d, {hours}h, {minutes}m, {seconds}s.**")


def setup(bot):
    bot.add_cog(Misc(bot))
