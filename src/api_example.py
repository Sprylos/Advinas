import asyncio
import infinitode as inf

# feel free to report errors (except event loop things, that's not my fault)


async def main():
    API = inf.Session()
    a = await API.runtime_leaderboards(mapname=5.1, playerid='U-E9BP-FSN9-H6ENMQ', difficulty='ENDLESS_I')
    b = await API.skill_point_leaderboard(playerid='U-E9BP-FSN9-H6ENMQ')
    c = await API.daily_quest_leaderboards(date=None, playerid='U-E9BP-FSN9-H6ENMQ')
    d = await API.leaderboards(5.1)
    e = await API.seasonal_leaderboard()
    f = await API.leaderboards_rank('5.1', 'U-E9BP-FSN9-H6ENMQ', mode='waves')
    g = await API.player('U-E9BP-FSN9-H6ENMQ')

    for i in (a, b, c, d, e):
        i.print_scores()
    print(f.playerid, f.rank)
    print(g.nickname, g.playerid, g.level, g.created_at)

    await API.close()

asyncio.run(main())
