import re
import slash_util
import discord
from discord.ext import commands
from discord.ext.commands import Context
from bot import Advinas
from dateutil import parser
from math import floor, ceil
from typing import Union
from exts.database import Database
from common.images import Images
from common.views import Paginator, ScorePaginator
from common.source import LBSource, ScoreLBSource
from common.utils import (
    BadChannel,
    answer,
    round_to_nearest,
    find_safe,
    get_level,
    get_level_bounty,
    codeblock,
    log,
    tablify,
    load_json
)


class Inf(slash_util.Cog):
    def __init__(self, bot: Advinas):
        super().__init__(bot)
        self.bot: Advinas
        self.mention_regex = re.compile(r'<@!?([0-9]+)>')
        self.playerid_regex = re.compile(
            r'U-([A-Za-z0-9]{4}-){2}[A-Za-z0-9]{6}')
        inf = load_json("data/inf.json")
        self.LEVELS: list[str] = list(inf['levels'].keys())
        self.LEVEL_INFO: dict[str: dict] = inf['levels']
        self.BOUNTY_DIFFS: dict[str: int] = inf['bountyDifficulties']
        self.EMOJIS: dict[str: int] = inf['enemy_emojis']
        self.images = Images()

    async def cog_check(self, ctx) -> bool:
        if ctx.guild and ctx.guild.id == 590288287864848387:
            if ctx.channel.id not in self.bot.BOT_CHANNELS:
                raise BadChannel('Command not used in an allowed channel.')
        return True

    async def slash_command_error(self, ctx, error: Exception) -> None:
        await self.bot.on_command_error(ctx, err=error)

    # Score command
    @slash_util.slash_command(name='score')
    async def _score(self, ctx: slash_util.Context, level: str):
        '''Shows the top 200 scores of the given level.'''
        await self.cog_check(ctx)
        await self.score(ctx, level=level)

    @commands.command(name='score', aliases=['s'])
    async def score(self, ctx: Union[Context, slash_util.Context], level: str):
        level = get_level(self.LEVELS, level)
        normal = (await self.bot.API.getLeaderboards(mapname=level))['leaderboards']
        endless = (await self.bot.API.getLeaderboards(mapname=level, difficulty='ENDLESS_I'))['leaderboards']
        await log(ctx)
        await ScorePaginator(source=ScoreLBSource(normal, endless, f'Level {level} Leaderboards (Score)', ctx)).start(ctx=ctx)

    # Wave command
    @slash_util.slash_command(name='waves')
    async def _waves(self, ctx: slash_util.Context, level: str):
        '''Shows the top 200 waves of the given level.'''
        await self.cog_check(ctx)
        await self.waves(ctx, level=level)

    @commands.command(name='waves', aliases=['w'])
    async def waves(self, ctx: Union[Context, slash_util.Context], level: str):
        level = get_level(self.LEVELS, level)
        normal = (await self.bot.API.getLeaderboards(mapname=level, mode='waves'))['leaderboards']
        endless = (await self.bot.API.getLeaderboards(mapname=level, mode='waves', difficulty='ENDLESS_I'))['leaderboards']
        await log(ctx)
        await ScorePaginator(source=ScoreLBSource(normal, endless, f'Level {level} Leaderboards (Waves)', ctx)).start(ctx=ctx)

    # Season command
    @slash_util.slash_command(name='season')
    async def _season(self, ctx: slash_util.Context):
        '''Shows the top 100 players of the season.'''
        await self.cog_check(ctx)
        await self.season(ctx)

    @commands.command(name='season', aliases=['sl', 'seasonal'])
    async def season(self, ctx: Union[Context, slash_util.Context]):
        data = await self.bot.API.seasonal_leaderboard()
        season, players, leaderboard = data['season'], data['NORMAL']['player_count'], data['NORMAL']['leaderboards']
        await log(ctx)
        await Paginator(source=LBSource(leaderboard, f'Season {season} Leaderboards', ctx, headline=f'Player Count: {players}')).start(ctx=ctx)

    # Dailyquest command
    @slash_util.slash_command(name='dailyquest')
    async def _dailyquest(self, ctx: slash_util.Context, date: str = None):
        '''Shows the top dailyquest scores of today or the given the day.'''
        await self.cog_check(ctx)
        await self.dailyquest(ctx, date=date)

    @commands.command(name='dailyquest', aliases=['dq'])
    async def dailyquest(self, ctx: Union[Context, slash_util.Context], date: str = None):
        if date:
            try:
                date = parser.parse(date, ignoretz=True).strftime('%Y-%m-%d')
            except:
                date = discord.utils.utcnow().strftime('%Y-%m-%d')
        leaderboard = (await self.bot.API.getDailyQuestLeaderboards(date=date))['leaderboards']
        if not leaderboard:
            entry = Database.find(self.bot.DB.dailyquests, date)
            if entry:
                leaderboard = entry.get(date, [])
        await log(ctx)
        await Paginator(source=LBSource(leaderboard, f'Dailyquest Leaderboards ({date})', ctx=ctx)).start(ctx)

    # Level command
    @slash_util.slash_command(name='level')
    async def _level(self, ctx: slash_util.Context, level: str):
        '''Shows useful information about the given level.'''
        await self.cog_check(ctx)
        await ctx.defer()
        await self.level(ctx, level=level)

    @commands.command(name='level', aliases=['l'])
    async def level(self, ctx: Union[Context, slash_util.Context], level: str):
        level = get_level(self.LEVELS, level)
        data = self.LEVEL_INFO[level]
        enemy_emojis = "".join(
            [f'<:enemy_{i.lower()}:{self.EMOJIS[f"enemy_{i.lower()}"]}>' for i in data["enemies"]])
        enemy_emojis = enemy_emojis or "None"
        filename = f'{level}.png'
        file = discord.File(f'assets/images/levels/{filename}')
        base = tablify(data["base"])
        quests = tablify(data["quests"])

        em = discord.Embed(title=f"Level {level} Info", colour=60415
                           ).set_image(url=f"attachment://{filename}"
                                       ).add_field(name="Difficulty", value=f"{data['difficulty']}%", inline=True
                                                   ).add_field(name="Enemies", value=enemy_emojis, inline=True)
        try:
            rt_lb = await self.bot.API.getRuntimeLeaderboards(level, "U-T68Z-T3JV-HK3DJY")
            em.add_field(name="Top 1% Threshold", value="{:,}".format(
                int(rt_lb['leaderboards'][200]['score'])))
        except:
            pass
        if base:
            em.add_field(name="Base Effects", value=base, inline=False)
        if quests:
            em.add_field(name="Quest Effects", value=quests, inline=False)

        await answer(ctx, embed=em, file=file)
        await log(ctx)

    # Bounty command
    @slash_util.slash_command(name='bounty')
    async def _bounty(self, ctx: slash_util.Context, coins: int = 65, difficulty: float = 100, bounties: int = 7, level: str = None):
        '''Calculates the optimal timings to place your bounties.'''
        await self.cog_check(ctx)
        await self.bounty(ctx, coins=coins, difficulty=difficulty, bounties=bounties, level=level)

    @commands.command(name='bounty', aliases=['b'])
    async def bounty(self, ctx: Union[Context, slash_util.Context], coins: int = 65, difficulty: float = 100, bounties: int = 7, level: str = None):
        level, difficulty, bounties, coins = get_level_bounty(
            self.BOUNTY_DIFFS, level=level, difficulty=difficulty, bounties=bounties, coins=coins)
        keep = coins * 50
        difSlope = 1+((difficulty-100)/200)
        lBounties, lCost, lBuy = [], [], []
        for i in range(1, bounties+1):
            val = floor((difSlope) * (1.60000002384186 **
                        (1.15 * (i - 1)) * 180))
            if val < 500:
                cost = round_to_nearest(val, 5)
            elif val < 5000:
                cost = round_to_nearest(val, 10)
            else:
                cost = round_to_nearest(val, 50)
            if (cost * i) < (coins * 50):
                buy = int((ceil(cost * (i - 1) / 50) * 50) + cost)
            else:
                buy = int((ceil(coins * (i - 1) / i) * 50) + cost)
            lBounties.append(str(i))
            lCost.append(str(cost))
            lBuy.append(str(find_safe(i=i, buy=buy, cost=cost, coins=coins)))

        description = f'Coins: `{coins}`\nDifficulty: `{difficulty}`\nKeepForMax: `{keep}`'
        if level:
            description += f'\nLevel: {level}'

        em = discord.Embed(
            title="Bounty Calculator", description=description, colour=60415
        ).set_footer(
            text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url
        ).add_field(
            name="Bounty", value=codeblock('\n'.join(lBounties)), inline=True
        ).add_field(
            name="Cost", value=codeblock('\n'.join(lCost)), inline=True
        ).add_field(
            name="Safe Buy", value=codeblock('\n'.join(lBuy)), inline=True)

        await answer(ctx, embed=em)
        await log(ctx)

    # Profile command
    @slash_util.slash_command(name='profile')
    async def _profile(self, ctx: slash_util.Context, playerid: str = None):
        '''Shows your in game profile in an image.'''
        await self.cog_check(ctx)
        await ctx.defer()
        await self.profile(ctx, playerid=playerid)

    @commands.command(name='profile', aliases=['p'])
    async def profile(self, ctx: Union[Context, slash_util.Context], playerid: str = None):
        dc_col, nn_col = self.bot.DB.discordnames, self.bot.DB.nicknames
        pl, player = None, None
        if not playerid:
            pl = Database.find(dc_col, ctx.author.id
                               ) or Database.find(nn_col, ctx.author.display_name
                                                  ) or Database.find(nn_col, ctx.author.name)
            if pl:
                player = await self.bot.API.player(playerid=next(iter(pl)))
            else:
                await log(ctx, success=False, reason='No player provided.')
                return await answer(ctx, content='Provide a player to search for.')
        elif self.playerid_regex.match(playerid):
            try:
                player = await self.bot.API.player(playerid=playerid)
            except:
                pass
            else:
                pl = {player.id: "<3"}
        if not player:
            pl = Database.find(nn_col, playerid)
            if not pl:
                match = self.mention_regex.search(playerid)
                new_id = match[0] if match else playerid
                pl = Database.find(dc_col, new_id)
                if not pl:
                    member = discord.utils.get(self.bot.users, name=playerid)
                    if member:
                        pl = Database.find(dc_col, member.id)
                    if not pl:
                        await log(ctx, success=False, reason='The provided player is invalid.')
                        return await answer(ctx, content='Could not find player. Check for spelling mistakes or try using '
                                            'the U- playerid from your profile page (Top left in the main menu).')
        if not player:
            player = await self.bot.API.player(playerid=next(iter(pl)))
        data = {player.id: {'name': player.name, 'key': player.name.lower()}}
        Database.update(nn_col, data=data)
        try:
            r = await self.bot.SESSION.get(player.avatar_link)
            avatar_bytes = await r.read()
        except:
            avatar_bytes = None

        final_buffer = await self.bot.loop.run_in_executor(None, self.images.profile_gen, player, avatar_bytes, ctx.author.id)

        file = discord.File(filename=f'{player.id}.png', fp=final_buffer)

        await answer(ctx, file=file)
        await log(ctx)


def setup(bot):
    bot.add_cog(Inf(bot))
