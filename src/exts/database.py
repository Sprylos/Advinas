import asyncio
import datetime
import discord
from discord.ext import commands, tasks
from bot import Advinas
from common.utils import load_json
from typing import Mapping
from pymongo.collection import Collection


class Database(commands.Cog):
    def __init__(self, bot: Advinas):
        self.bot = bot
        inf = load_json("data/inf.json")
        self._levels: list[str] = list(l if not l.startswith(
            'dq') else l.upper() for l in inf['levels'].keys())
        bot.loop.create_task(self.ready())

    async def ready(self):
        await self.bot.wait_until_ready()
        # make sure the DB is ready
        await asyncio.sleep(1)
        self._discords, self._nicks, self._dailyquests = self.bot.DB.discordnames, self.bot.DB.nicknames, self.bot.DB.dailyquests
        self.save_dailyquest_leaderboard.start()
        # self.eval_leaderboards.start() # don't

    @staticmethod
    def find(col: Collection, data):
        return col.find_one({"$text": {"$search": str(data)}}, {'_id': 0})

    @staticmethod
    def find_by_key(col: Collection, data):
        return col.find_one({str(data): {'$exists': True}})

    @staticmethod
    def update(col: Collection, data):
        if not isinstance(data, Mapping):
            for document in data:
                col.update_one(filter=document,
                               update={"$set": document}, upsert=True)
        else:
            col.update_one(filter=data,
                           update={"$set": data}, upsert=True)

    # this call is ok. Rainys server allows it just fine
    async def get_all_leaderboards(self) -> dict[str: list[dict]]:
        ret = dict()
        for level in self._levels:
            ret[level] = await self.bot.API.leaderboards(level)
        return ret

    # this however is a dumb thing to do. It will make 12600 database calls and stop the bots for several minutes.
    # I will fix it soon-ish.
    def _get_all_players(self, all_leaderboards: dict) -> set[dict[str: str]]:
        players = list()
        for _, leaderboard in all_leaderboards.items():
            for score in leaderboard:
                players.append({score.playerid: {'name': score.nickname, 'key': score.nickname.lower()}})  # nopep8
        self._add_new_players(players)
        return players

    # adds unknown players to the db so you don't always need to use the playerid on the first time
    def _add_new_players(self, players=None):
        return self.update(self._nicks, data=players)

    # 12 hours just in case something goes wrong, we have a smaller chance of missing a day
    @tasks.loop(hours=12)
    async def save_dailyquest_leaderboard(self):
        # we save yesterday because that leaderboard can't change anymore.
        # if we saved the current day we could miss some late players
        date = (discord.utils.utcnow() -
                datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        leaderboards = await self.bot.API.daily_quest_leaderboards(date, raw=True)
        data = {date: leaderboards['leaderboards']}
        self.update(self._dailyquests, data=data)
        print('updated')

    # this is very expensive.
    @tasks.loop(hours=12)
    async def eval_leaderboards(self):
        print('started')
        all_leaderboards = await self.get_all_leaderboards()
        print('got all')
        self._get_all_players(all_leaderboards)
        print('synced')


def setup(bot):
    bot.add_cog(Database(bot))
