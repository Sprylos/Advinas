from __future__ import annotations

# std
import asyncio
import datetime
from typing import Any, Mapping, TYPE_CHECKING

# packages
import discord
from discord.ext import commands, tasks
from infinitode import Leaderboard

# local
from common.utils import load_json

if TYPE_CHECKING:
    from bot import Advinas


class Database(commands.Cog):
    def __init__(self, bot: Advinas):
        self.bot = bot
        inf = load_json("data/inf.json")
        self._levels: list[str] = list(
            l if not l.startswith("dq") else l.upper() for l in inf["levels"].keys()
        )
        bot.loop.create_task(self.ready())

    async def ready(self):
        await self.bot.wait_until_ready()
        # make sure the DB is ready
        await asyncio.sleep(3)
        self._discords, self._nicks, self._dailyquests = (
            self.bot.DB.discordnames,
            self.bot.DB.nicknames,
            self.bot.DB.dailyquests,
        )
        self.save_dailyquest_leaderboard.start()
        # await self.eval_leaderboards() # don't

    @staticmethod
    async def find(col, data: Any) -> Any:
        return await col.find_one({"$text": {"$search": str(data)}}, {"_id": 0})

    @staticmethod
    async def find_by_key(col, data: Any) -> Any:
        return await col.find_one({str(data): {"$exists": True}})

    @staticmethod
    async def update(col, data: Any) -> None:
        if not isinstance(data, Mapping):
            for document in data:
                await col.update_one(
                    filter=document, update={"$set": document}, upsert=True
                )
        else:
            await col.update_one(filter=data, update={"$set": data}, upsert=True)

    # this call is ok. Rainys server allows it just fine
    async def get_all_leaderboards(
        self, mode: str = "score", difficulty: str = "NORMAL"
    ) -> dict[str, Leaderboard]:
        ret: dict[str, Leaderboard] = dict()
        for level in self._levels:
            try:
                ret[level] = await self.bot.API.leaderboards(
                    level, mode=mode, difficulty=difficulty
                )
            except Exception:
                pass
        return ret

    async def _get_all_players(
        self, all_leaderboards: dict[Any, Leaderboard]
    ) -> list[dict[str, Any]]:
        players: list[dict[str, Any]] = list()
        for _, leaderboard in all_leaderboards.items():
            for score in leaderboard:
                if score.nickname is not None:
                    players.append(
                        {
                            score.playerid: {
                                "name": score.nickname,
                                "key": score.nickname.lower(),
                            }
                        }
                    )
        await self._add_new_players(players)
        return players

    # adds unknown players to the db so you don't always need to use the playerid on the first time
    async def _add_new_players(self, players: list[dict[str, Any]]):
        return await self.update(self._nicks, data=players)

    # 12 hours just in case something goes wrong, we have a smaller chance of missing a day
    @tasks.loop(hours=12)
    async def save_dailyquest_leaderboard(self):
        # we save yesterday because that leaderboard can't change anymore.
        # if we saved the current day we could miss some late players
        date = (discord.utils.utcnow() - datetime.timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )
        leaderboards = await self.bot.API.daily_quest_leaderboards(date)

        data = {date: leaderboards.raw["leaderboards"]}
        await self.update(self._dailyquests, data=data)
        
        await self.bot.task_completion(self.save_dailyquest_leaderboard, fields={"Date": date})

    @save_dailyquest_leaderboard.error
    async def task_error(self, err: BaseException):
        await self.bot.task_error(self.save_dailyquest_leaderboard, err)

    # this is very expensive.
    async def eval_leaderboards(self):
        print("started")
        all_leaderboards = await self.get_all_leaderboards(difficulty="ENDLESS_I")
        all_leaderboards2 = await self.get_all_leaderboards(
            mode="waves", difficulty="ENDLESS_I"
        )
        print("got all")
        await self._get_all_players(all_leaderboards)
        await self._get_all_players(all_leaderboards2)
        print("synced")


async def setup(bot: Advinas):
    await bot.add_cog(Database(bot))
