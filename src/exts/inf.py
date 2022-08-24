from __future__ import annotations

# std
import re
import time
from math import floor, ceil
from typing import Annotated, Any, TYPE_CHECKING


# packages
import aiohttp
import discord
from discord import Interaction, app_commands
from discord.ext import commands
from infinitode import Player, Leaderboard
from infinitode.errors import APIError, BadArgument
from motor.motor_asyncio import AsyncIOMotorCollection

# local
from exts.database import Database
from common.images import Images
from common.custom import Context, LevelConverter
from common.views import Paginator, ScorePaginator
from common.source import LBSource, ScoreLBSource
from common.utils import (
    create_choices,
    round_to_nearest,
    find_safe,
    get_level_bounty,
    codeblock,
    tablify,
    load_json,
)
from common.errors import (
    BadChannel,
    InvalidDateError,
    InvalidPlayerError,
    NoPlayerProvidedError,
)

if TYPE_CHECKING:
    from bot import Advinas


class Inf(commands.Cog):
    def __init__(self, bot: Advinas):
        super().__init__()
        self.bot: Advinas = bot
        self.mention_regex = re.compile(r'<@!?([0-9]+)>')
        inf = load_json("data/inf.json")
        self.LEVELS: list[str] = list(inf['levels'].keys())
        self.bot.LEVELS = self.LEVELS
        self.LEVEL_INFO: dict[str, dict[str, Any]] = inf['levels']
        self.BOUNTY_DIFFS: dict[str, int | float] = inf['bountyDifficulties']
        self.EMOJIS: dict[str, int] = inf['enemy_emojis']
        self.images = Images()
        bot.loop.create_task(self.ready())

    async def ready(self):
        await self.bot.wait_until_ready()
        payload: list[dict[str, Any]] = await self.bot.DB.nicknames.find({}, {'_id': 0}).to_list(None)  # nopep8
        self.PLAYERIDS = {next(iter(doc.values()))['key'] for doc in payload} | {
            next(iter(doc)) for doc in payload}

    def cog_check(self, ctx: Context) -> bool:
        if ctx.guild and ctx.guild.id == 590288287864848387:
            if ctx.channel.id not in self.bot.BOT_CHANNELS:
                raise BadChannel
        return True

    # Score command
    @commands.hybrid_command(name='score', aliases=['sc'], description='Shows the top 200 scores of the given level.')
    @app_commands.describe(level='The level which you want to see the score leaderboard for.')
    async def score(self, ctx: Context, level: Annotated[str, LevelConverter]):
        normal = await self.bot.API.leaderboards(level)
        endless = await self.bot.API.leaderboards(level, difficulty='ENDLESS_I')

        await ScorePaginator(ScoreLBSource(ctx, normal, endless, f'Level {level} Leaderboards (Score)')).start(ctx)

    # Wave command
    @commands.hybrid_command(name='waves', aliases=['w'], description='Shows the top 200 waves of the given level.')
    @app_commands.describe(level='The level which you want to see the wave leaderboard for.')
    async def waves(self, ctx: Context, level: Annotated[str, LevelConverter]):
        normal = await self.bot.API.leaderboards(level, mode='waves')
        endless = await self.bot.API.leaderboards(level, mode='waves', difficulty='ENDLESS_I')

        await ScorePaginator(ScoreLBSource(ctx, normal, endless, f'Level {level} Leaderboards (Waves)')).start(ctx)

    # Season command
    @commands.hybrid_command(name='season', aliases=['sl', 'seasonal'], description='Shows the top 100 players of the season.')
    async def season(self, ctx: Context):
        await ctx.defer()
        lb = await self.bot.API.seasonal_leaderboard()

        await Paginator(LBSource(ctx, lb, f'Season {lb.season} Leaderboards',  headline=f'Player Count: {lb.total}')).start(ctx)

    # Dailyquest command
    @commands.hybrid_command(name='dailyquest', aliases=['dq'], description='Shows the top dailyquest scores of today or the given the day.')
    @app_commands.describe(date='The date you want to see the leaderboard for. Only available beyond 2022-02-09. FORMAT: YYYY-MM-DD!')
    async def dailyquest(self, ctx: Context, date: str | None = None):
        lb = await self.bot.API.daily_quest_leaderboards(date, warning=False)
        if lb.is_empty:
            entry = await Database.find_by_key(self.bot.DB.dailyquests, date)
            try:
                scores = entry.get(lb.date)
            except (AttributeError, KeyError):
                raise InvalidDateError from None
            payload = {'player': {'total': 69420}, 'leaderboards': scores}
            lb = Leaderboard.from_payload(
                '', '', '', '', None, payload, date=lb.date)

        ctx.kwargs['date'] = lb.date

        await Paginator(LBSource(ctx, lb, f'Dailyquest Leaderboards ({lb.date})')).start(ctx)

    # Level command
    @commands.hybrid_command(name='level', aliases=['lvl'], description='Shows useful information about the given level.')
    @app_commands.describe(level='The level which you want to see information for.')
    async def level(self, ctx: Context, level: Annotated[str, LevelConverter]):
        data = self.LEVEL_INFO[level.lower(
        ) if level.startswith('DQ') else level]
        enemy_emojis = "".join(
            [f'<:enemy_{i.lower()}:{self.EMOJIS[f"enemy_{i.lower()}"]}>' for i in data["enemies"]])
        enemy_emojis = enemy_emojis or "None"
        filename = f'{level}.png'
        file = discord.File(f'assets/images/levels/{filename}')
        base = tablify(data["base"])
        quests = tablify(data["quests"])

        em = discord.Embed(title=f"Level {level} Info", colour=60415)
        em.set_image(url=f"attachment://{filename}")
        em.add_field(name="Difficulty", value=f"{data['difficulty']}%", inline=True)  # nopep8
        em.add_field(name="Enemies", value=enemy_emojis, inline=True)
        em.set_footer(
            text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        try:
            rt_lb = await self.bot.API.runtime_leaderboards(level, "U-T68Z-T3JV-HK3DJY")
            em.add_field(name="Top 1% Threshold", value="{:,}".format(int(rt_lb[200].score)))  # nopep8
        except (APIError, BadArgument):
            pass
        if base:
            em.add_field(name="Base Effects", value=base, inline=False)
        if quests:
            em.add_field(name="Quest Effects", value=quests, inline=False)

        await ctx.reply(embed=em, file=file)

    # Bounty command

    @commands.hybrid_command(name='bounty', aliases=['b'], description='Calculates the optimal timings to place your bounties.')
    @app_commands.describe(
        coins='The maximum amount of coins a bounty gives you per round. Cap: 200. DEFAULT: 65',
        difficulty='The portal difficulty you are playing on. Cap: 4500. DEFAULT: 100',
        bounties='The number of bounties you have. Cap: 12. DEFAULT: 7',
        level='If a level is provided, the level\'s difficulty will take priority over the given difficulty.',
    )
    async def bounty(self, ctx: Context, coins: int = 65, difficulty: float = 100.0, bounties: int = 7, level: str | None = None):
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
            description += f'\nLevel: `{level}`'

        em = discord.Embed(
            title="Bounty Calculator", description=description, colour=60415
        ).set_footer(
            text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url
        ).add_field(
            name="Bounty", value=codeblock('\n'.join(lBounties)), inline=True
        ).add_field(
            name="Cost", value=codeblock('\n'.join(lCost)), inline=True
        ).add_field(
            name="Safe Buy", value=codeblock('\n'.join(lBuy)), inline=True)

        await ctx.reply(embed=em)

    @score.autocomplete('level')
    @waves.autocomplete('level')
    @level.autocomplete('level')
    @bounty.autocomplete('level')
    async def level_autocomplete(self, inter: Interaction, current: str) -> list[app_commands.Choice[str]]:
        return create_choices({i for i in self.LEVELS if i.startswith(current.lower()) or current.lower() in i})

    # Profile command
    @commands.hybrid_command(name='profile', aliases=['prof'], description='Shows your in game profile in an image (NO ENDLESS LEADERBOARD DUE TO API LIMITATIONS).')
    @app_commands.describe(playerid='The playerid of the player you want to see the profile of.')
    async def profile(self, ctx: Context, playerid: str | None = None) -> Any:
        await ctx.defer()
        dc_col: AsyncIOMotorCollection = self.bot.DB.discordnames
        nn_col: AsyncIOMotorCollection = self.bot.DB.nicknames
        pl: dict[str, Any] = {}
        player: Player | None = None
        start_time: float = time.perf_counter()
        if playerid is None:  # no playerid was given
            pl = await Database.find(dc_col, str(ctx.author.id)
                                     ) or await Database.find(nn_col, ctx.author.display_name
                                                              ) or await Database.find(nn_col, ctx.author.name)
            if pl:  # the playerid was found in the database using info about the author
                player = await self.bot.API.player(playerid=next(iter(pl)))
                playerid = ''  # make typechecker happy
            else:
                raise NoPlayerProvidedError
        else:
            try:
                upper = playerid.upper()
                player = await self.bot.API.player(playerid=upper if upper.startswith('U-') else 'U-' + upper)
            except (APIError, BadArgument):
                pass  # The playerid is invalid, but we don't give up yet
            else:
                pl = {player.playerid: "<3"}
        if not player:  # still no luck
            pl = await Database.find(nn_col, playerid)
            if not pl:
                match = self.mention_regex.search(playerid)
                new_id = match[0] if match else playerid
                pl = await Database.find(dc_col, new_id)
                if not pl:
                    member = discord.utils.get(self.bot.users, name=playerid)
                    if member:
                        pl = await Database.find(dc_col, str(member.id))
                    if not pl:
                        raise InvalidPlayerError
        if not player:
            player = await self.bot.API.player(playerid=next(iter(pl)))
        data = {player.playerid: {
            'name': player.nickname, 'key': player.nickname.lower()}}
        await Database.update(nn_col, data=data)
        try:
            r = await self.bot.session.get(player.avatar_link)
            r.raise_for_status()
            avatar_bytes = await r.read()
        except aiohttp.ClientResponseError:
            avatar_bytes = None
        await player.fetch_daily_quest(self.bot.API)
        await player.fetch_skill_point(self.bot.API)

        final_buffer = await self.bot.loop.run_in_executor(None, self.images.profile_gen, player, avatar_bytes, ctx.author.id)

        file = discord.File(filename=f'{player.playerid}.png', fp=final_buffer)
        await ctx.reply(f'Finished in {time.perf_counter() - start_time:0.3f}s', file=file)

    @profile.autocomplete('playerid')
    async def playerid_autocomplete(self, inter: Interaction, current: str) -> list[app_commands.Choice[str]]:
        return create_choices({i for i in self.PLAYERIDS if i.startswith(current.lower()) or current.lower() in i})


async def setup(bot: Advinas):
    await bot.add_cog(Inf(bot))
