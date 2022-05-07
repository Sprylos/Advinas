# packages
import discord
from discord.ext import commands

# local
from bot import Advinas
from common.views import Invite
from common.custom import BadChannel, Context


class Misc(commands.Cog):
    def __init__(self, bot: Advinas):
        self.bot: Advinas = bot
        super().__init__()

    def cog_check(self, ctx: Context) -> bool:
        if ctx.guild and ctx.guild.id == 590288287864848387:
            if ctx.channel.id not in self.bot.BOT_CHANNELS:
                raise BadChannel('Command not used in an allowed channel.')
        return True

    # ping command
    @commands.hybrid_command(name='ping', description='Shows the bot\'s latency.')
    async def ping(self, ctx: Context):
        await ctx.reply(f'Latency: {round(self.bot.latency * 1000)}ms.', ephemeral=True)
        await ctx.log()

    # invite command
    @commands.hybrid_command(name='invite', description='Gives you a link to invite the bot to your own server.')
    async def invite(self, ctx: Context):
        em = discord.Embed(
            description=r'[Invite The Bot](https://discord.com/api/oauth2/authorize?client_id=824289599065030756&permissions=309238025280&scope=bot%20applications.commands)'
        ).set_footer(
            text=f'Requested by {ctx.author}', icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=em, view=Invite())
        await ctx.log()

    # uptime command
    @commands.hybrid_command(name='uptime', description='Shows the bots uptime since the last reboot.')
    async def uptime(self, ctx: Context):
        delta_uptime = discord.utils.utcnow() - self.bot.online_since
        hours, remainder = divmod(int(delta_uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        await ctx.reply(content=f"Time since last reboot: **{days}d, {hours}h, {minutes}m, {seconds}s.**")
        await ctx.log()


async def setup(bot: Advinas):
    await bot.add_cog(Misc(bot))
