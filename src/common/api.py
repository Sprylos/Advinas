import aiohttp
from time import time
from datetime import datetime as dt
from bs4 import BeautifulSoup, Comment


class APIError(Exception):
    '''API Error'''
    pass


class APIData:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.cooldown = {'RuntimeLeaderboards': {}, 'DailyQuestInfo': 0, 'LatestNews': 0, 'DailyQuestLeaderboards': {
        }, 'SkillPointLeaderboard': 0, 'BasicLevelsTopLeaderboards': {}, 'Leaderboards': {}, 'seasonal': 0}
        self.DailyQuestLeaderboards = {}
        self.BasicLevelsTopLeaderboards = {}
        self.Leaderboards = {}
        self.RuntimeLeaderboards = {}

    async def post(self, arg, data: dict = None):
        url = f'https://infinitode.prineside.com/?m=api&a={arg}&apiv=1&g=com.prineside.tdi2&v=282'
        async with self.session.post(url, data=data) as r:
            try:
                r.raise_for_status()
            except:
                raise APIError(
                    "Something went wrong. Maybe Rainy's servers are on fire. Try again later")

            data = await r.json()

            if data.get('status') == 'success':
                return data
            else:
                print(data)
                raise APIError('The returned data is invalid. Try again later')

    async def getRuntimeLeaderboards(self, mapname, playerid, mode='score', difficulty='NORMAL'):
        key = f'{difficulty}{mode}{mapname}'
        if time() < self.cooldown['RuntimeLeaderboards'].get(key, 0) + 60 and not playerid:
            return self.RuntimeLeaderboards[key]

        data = await self.post('getRuntimeLeaderboards', data={
            'gamemode': 'BASIC_LEVELS', 'difficulty': difficulty, 'playerid': playerid, 'mapname': mapname, 'mode': mode})
        if not playerid:
            self.RuntimeLeaderboards[key] = data
            self.cooldown['RuntimeLeaderboards'][key] = time()

        return data

    async def getDailyQuestInfo(self):
        if time() < self.cooldown['DailyQuestInfo'] + 60:
            return self.DailyQuestInfo
        self.DailyQuestInfo = await self.post('getDailyQuestInfo')
        self.cooldown['DailyQuestInfo'] = time()

        return self.DailyQuestInfo

    async def getLatestNews(self, locale='en_US'):
        if time() < self.cooldown['LatestNews'] + 60:
            return self.LatestNews

        self.LatestNews = await self.post('getLatestNews')
        self.cooldown['LatestNews'] = time()

        return self.LatestNews

    async def getSkillPointLeaderboard(self, playerid=None):
        if time() < self.cooldown['SkillPointLeaderboard'] + 60 and not playerid:
            return self.SkillPointLeaderboard
        data = await self.post('getSkillPointLeaderboard',
                               data={'playerid': playerid})

        if playerid:
            for x in data['player']:
                data['player'][x] = int(data['player'][x])
        if not playerid:
            self.SkillPointLeaderboard = data
            self.cooldown['SkillPointLeaderboard'] = time()

        return data

    async def getDailyQuestLeaderboards(self, date=None, playerid=None):
        if date == None:
            date = dt.utcnow().strftime('%Y-%m-%d')
        if not playerid and (time() < self.cooldown['DailyQuestLeaderboards'].get(date, 0) + 60):
            return self.DailyQuestLeaderboards[date]
        data = await self.post('getDailyQuestLeaderboards', data={
            'date': date, 'playerid': playerid})

        for x in data['leaderboards']:
            x['score'] = int(x['score'])
        if playerid:
            for x in data['player']:
                data['player'][x] = int(data['player'][x])
        if not playerid:
            self.DailyQuestLeaderboards[date] = data
            self.cooldown['DailyQuestLeaderboards'][date] = time()

        return data

    async def getBasicLevelsTopLeaderboards(self, mode='score'):
        key = str(mode)
        if time() < self.cooldown['BasicLevelsTopLeaderboards'].get(key, 0) + 60:
            return self.BasicLevelsTopLeaderboards[key]
        self.BasicLevelsTopLeaderboards[key] = await self.post('getBasicLevelsTopLeaderboards', data={'mode': mode})

        t = {
            'status': self.BasicLevelsTopLeaderboards[key]['status'], 'levels': {}}
        for x in self.BasicLevelsTopLeaderboards[key]['levels']:
            t['levels'][x['level']] = {'leaderboards': x['leaderboards']}
        for x in t['levels']:
            for y in t['levels'][x]['leaderboards']:
                y['score'] = int(y['score'])
        self.BasicLevelsTopLeaderboards[key] = t
        self.cooldown['BasicLevelsTopLeaderboards'][key] = time()

        return self.BasicLevelsTopLeaderboards[key]

    async def getLeaderboardsRank(self, mapname, playerid, mode='score', difficulty='NORMAL'):
        return await self.post('getLeaderboardsRank', data={'gamemode': 'BASIC_LEVELS', 'difficulty': difficulty, 'playerid': playerid, 'mapname': mapname, 'mode': mode})

    async def getLeaderboards(self, mapname, playerid=None, mode='score', difficulty='NORMAL'):
        key = f'{difficulty}{mode}{mapname}'
        if not playerid and (time() < self.cooldown['Leaderboards'].get(key, 0) + 60):
            return self.Leaderboards[key]
        data = await self.post('getLeaderboards', data={'gamemode': 'BASIC_LEVELS', 'difficulty': difficulty, 'playerid': playerid, 'mapname': mapname, 'mode': mode})

        for x in data['leaderboards']:
            x['score'] = int(x['score'])
        if not playerid:
            self.Leaderboards[key] = data
            self.cooldown['Leaderboards'][key] = time()

        return data

    async def seasonal_leaderboard(self):
        if time() < self.cooldown['seasonal'] + 60:
            return self.seasonal
        url = f'https://infinitode.prineside.com/xdx/?url=seasonal_leaderboard'
        r = await self.session.get(url=url)
        try:
            r.raise_for_status()
        except aiohttp.ClientResponseError:
            raise APIError('Bad Gateway')
        self.seasonal = BeautifulSoup(await r.text(), 'lxml')
        t = {}

        t['status'] = 'success'
        t['season'] = int(self.seasonal.select_one('label[i18n="season_formatted"]')[
                          'i18nf'].replace('["', '').replace('"]', ''))
        t['NORMAL'] = {}
        t['NORMAL']['player_count'] = int(self.seasonal.select('label[i18n="player_count_formatted"]')[
                                          0]['i18nf'].replace('["', '').replace('"]', '').replace(',', ''))
        t['NORMAL']['leaderboards'] = []
        for x in range(len(self.seasonal.select('div[x="90"]'))):
            t['NORMAL']['leaderboards'].append({'playerid': self.seasonal.select('label[color="LIGHT_BLUE:P300"]')[x]['click'].split('id=')[1], 'nickname': self.seasonal.select(
                'label[color="LIGHT_BLUE:P300"]')[x].text, 'score': int(self.seasonal.select('label[nowrap="true"][text-align="right"]')[x].text.replace(',', ''))})
        self.seasonal = t
        self.cooldown['seasonal'] = time()

        return self.seasonal

    async def profile(self, playerid):
        url = f'https://infinitode.prineside.com/xdx/index.php?url=profile/view&id={playerid}'
        r = await self.session.get(url=url)
        try:
            r.raise_for_status()
        except aiohttp.ClientResponseError:
            raise APIError('Bad Gateway')
        data = BeautifulSoup(await r.text(), 'lxml')
        t = {}

        t['status'] = 'success'
        t['id'] = playerid
        t['name'] = data.select_one('label:not([i18n])').text
        try:
            t['season'] = int(data.select_one('label[i18n="season_formatted"]')[
                'i18nf'].replace('["', '').replace('"]', ''))
        except:
            t['season'] = 0
        try:
            t['score'] = int(data.select_one(
                'div[width="522"][height="128"][pad-top="10"][pad-bottom="10"][align="center"]').select('label')[1].text.replace(',', ''))
        except:
            t['score'] = 0
        try:
            t['rank'] = int(data.select_one(
                'div[width="522"][height="128"][pad-top="10"][pad-bottom="10"][align="center"]').select('label')[2].text.replace(',', ''))
        except:
            t['rank'] = 0
        try:
            t['top'] = data.select_one(
                'div[width="522"][height="128"][pad-top="10"][pad-bottom="10"][align="center"]').select('label')[3].text.replace('- Top ', '')
        except:
            t['top'] = 0
        comments = data.findAll(
            text=lambda text: isinstance(text, Comment))
        for x in comments:
            if 'Level:' in x:
                t['level'] = int(x.split('>')[3].split('<')[0])
                break
        t['xp'] = int(data.select_one('div[width="330"][height="64"]').select_one(
            'label').text.split(' / ')[0])
        t['xp_max'] = int(data.select_one(
            'div[width="330"][height="64"]').select_one('label').text.split(' / ')[1])
        t['levels'] = {}
        for x in data.select('div[width="800"][height="40"]')[1:]:
            t['levels'][x.select('label')[0].text] = {'rank': int(x.select('label')[2].text.replace(',', '')), 'score': int(x.select('label')[1].text.replace(',', '')), 'total': int(x.select('label')[
                3].text.replace('/ ', '').replace(',', '')), 'top': x.select('label')[-1].text} if not x.select_one('label[i18n="not_ranked"]') else {'rank': 0, 'score': 0, 'total': 0, 'top': '-%'}
        t['badges'] = {}
        for x in data.select('div[width="80"][height="80"]'):
            rar = x.select('img')[0]['src'].split('bg-')[1]
            if rar in ['not-received', 'common', 'rare', 'very-rare', 'epic', 'legendary', 'supreme', 'artifact']:
                ico = x.select('img')[1]['src'].split('icon-')[1]
                if ico in ['daily-game', 'invited-players', 'killed-enemies', 'mined-resources', 'of-merit', 'beta-tester-season-2'] or ico[:8] == 'season-1':
                    col = x.select('img')[-1]['color']
                    t['badges'][ico] = (rar, col)
        labels = data.select(
            'table[width="800"][align="center"]')[-1].select('label')
        t['replays'] = int(labels[-3].string.split(" ")[3])
        t['issues'] = int(labels[-2].string.split(" ")[0][3:])
        sp = list(labels[-1].string.split("ned ")[1].split(" "))
        day = sp[0][:-2] if len(sp[0][:2]) == 2 else "0" + sp[0][:2]
        t['created_at'] = str(dt.strptime(
            day + " " + sp[-2] + " " + sp[-1], "%d %B %Y").strftime("%d.%m.%Y"))

        return t

    async def player(self, playerid):
        return Player(await self.profile(playerid), await self.getDailyQuestLeaderboards(playerid=playerid), await self.getSkillPointLeaderboard(playerid=playerid))


class Player:
    def __init__(self, profile: dict, dailyquest, skillpoint):
        self.profile: dict = profile
        self.levels: dict[str: dict] = self.profile['levels']
        self.id: str = self.profile['id']
        self.avatar_link: str = f'https://infinitode.prineside.com/img/avatars/{self.id}-128.png'
        self.name: str = self.profile['name']
        self.xp: int = self.profile['xp']
        self.level: int = self.profile['level']
        self.xp_max: int = self.profile['xp_max']
        self.dailyquest: dict = dailyquest['player']
        self.skillpoint: dict = skillpoint['player']
        self.badges: dict[str: tuple[str, str]] = self.profile['badges']
        self.total_score: int = self.profile['score']
        self.total_rank: int = self.profile['rank']
        self.total_top: str = self.profile['top']
        self.replays: int = self.profile['replays']
        self.issues: int = self.profile['issues']
        self.created_at: str = self.profile['created_at']

    def score(self, level):
        return self.levels.get(level, {'rank': 0, 'score': 0, 'total': 0, 'top': '-%'})


if __name__ == '__main__':
    # testing
    async def main():
        async with aiohttp.ClientSession() as s:
            API = APIData(s)
            a = await API.getRuntimeLeaderboards(mapname='5.1', playerid='U-E9BP-FSN9-H6ENMQ', mode='score', difficulty='NORMAL')
            b = await API.getDailyQuestInfo()
            c = await API.getLatestNews()
            d = await API.getSkillPointLeaderboard(playerid='U-E9BP-FSN9-H6ENMQ')
            e = await API.getDailyQuestLeaderboards(date=None, playerid='U-E9BP-FSN9-H6ENMQ')
            f = await API.getBasicLevelsTopLeaderboards(mode='score')
            g = await API.getLeaderboardsRank(mapname='5.1', playerid='U-E9BP-FSN9-H6ENMQ', mode='score', difficulty='NORMAL')
            h = await API.getLeaderboards(mapname='5.1', playerid='U-E9BP-FSN9-H6ENMQ', mode='score', difficulty='NORMAL')
            i = await API.seasonal_leaderboard()
            j = await API.profile('U-E9BP-FSN9-H6ENMQ')

            content = f'RUNTIMELEADERBOARDS:\n{a}\n\nDAILYQUESTINFO\n{b}\n\nLATESTNEWS\n{c}\n\nSKILLPOINTLEADERBOARD\n{d}\n\nDAILYQUESTLEADERBOARDS\n{e}\n\n\
                   BASICLEVELSTOPLEADERBOARDS\n{f}\n\nLEADERBOARDSRANK\n{g}\n\nLEADERBOARDS\n{h}\n\nSEASONAL_LEADERBOARD\n{i}\n\nPROFILE\n{j}'

            with open('temp.txt', 'w', encoding='utf-8') as f:
                f.write(content)

    import asyncio
    asyncio.run(main())
