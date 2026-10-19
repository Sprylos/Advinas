from __future__ import annotations

# std
import asyncio
import datetime
import logging
from typing import TYPE_CHECKING, Any, Mapping, Sequence

# packages
import discord
from discord.ext import commands, tasks
from motor.motor_asyncio import AsyncIOMotorCollection

# local
if TYPE_CHECKING:
    from bot import Advinas


class Database(commands.Cog):
    def __init__(self, bot: Advinas):
        self.bot = bot
        self.ready_task = bot.loop.create_task(self.ready())

    async def ready(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(3)
        self.dailyquest = self.bot.DB.dailyquest
        self.save_dailyquest_leaderboard.start()
        self.save_dailyquest_metadata.start()

    async def cog_unload(self):
        self.ready_task.cancel()
        self.save_dailyquest_metadata.cancel()
        self.save_dailyquest_leaderboard.cancel()
        pending = [
            self.ready_task,
            self.save_dailyquest_metadata.get_task(),
            self.save_dailyquest_leaderboard.get_task(),
        ]
        await asyncio.gather(
            *(task for task in pending if task is not None), return_exceptions=True
        )

    @tasks.loop(hours=1)
    async def save_dailyquest_metadata(self):
        try:
            async with asyncio.timeout(30):
                info = await self.bot.API.daily_quest_info()
                now = discord.utils.utcnow()
                if (
                    info.date != now.date().isoformat()
                    or info.reset_timestamp <= now.timestamp()
                ):
                    raise ValueError("Daily Quest metadata is not current")
                await self.upsert(
                    self.dailyquest,
                    {"date": info.date},
                    data={
                        "live_metadata": {
                            "quest_id": info.quest_id,
                            "mapname": info.mapname,
                            "reset_timestamp": info.reset_timestamp,
                            "data_hash": info.data_hash,
                            "source": "official",
                            "captured_at": now.isoformat(),
                        }
                    },
                )
        except Exception:
            logging.getLogger(__name__).warning(
                "Daily Quest metadata capture failed; retrying next hour"
            )

    @staticmethod
    async def find_by_key(col: AsyncIOMotorCollection, data: Any) -> Any:
        return await col.find_one({str(data): {"$exists": True}})

    @staticmethod
    async def upsert(
        col: AsyncIOMotorCollection,
        filter: Sequence[Any] | Mapping[Any, Any],
        data: Sequence[Any] | Mapping[Any, Any],
    ) -> None:
        if isinstance(data, Mapping) and isinstance(filter, Mapping):
            await col.update_one(filter=filter, update={"$set": data}, upsert=True)
            return

        if isinstance(data, Sequence) and isinstance(filter, Sequence):
            if len(data) != len(filter):
                return

            for index, document in enumerate(data):
                await col.update_one(
                    filter=filter[index], update={"$set": document}, upsert=True
                )

    # 12 hours just in case something goes wrong, we have a smaller chance of missing a day
    @tasks.loop(hours=12)
    async def save_dailyquest_leaderboard(self):
        # we save yesterday because that leaderboard can't change anymore.
        # if we saved the current day we could miss some late players
        date = (discord.utils.utcnow() - datetime.timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )
        lb = await self.bot.API.daily_quest_leaderboards(date)
        lb_beta = await self.bot.API.daily_quest_leaderboards(date=date, beta=True)

        data = {
            "date": date,
            "live": {"total": lb.total, "leaderboards": lb.raw["leaderboards"]},
            "beta": {
                "total": lb_beta.total,
                "leaderboards": lb_beta.raw["leaderboards"],
            },
        }
        await self.upsert(self.dailyquest, {"date": date}, data=data)

        await self.bot.task_completion(
            self.save_dailyquest_leaderboard, fields={"Date": date}
        )

    @save_dailyquest_leaderboard.error
    async def task_error(self, err: BaseException):
        await self.bot.task_error(self.save_dailyquest_leaderboard, err)


async def setup(bot: Advinas):
    await bot.add_cog(Database(bot))
