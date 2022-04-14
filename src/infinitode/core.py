# std
import re
import time
import datetime

# packages
import aiohttp
import bs4
from dateutil import parser
from typing import Union, Tuple

# local
from .models import APIError
from .models import Leaderboard
from .models import Player
from .models import Score


__all__ = ["Session"]

ID_REGEX = re.compile(r'U-([A-Z0-9]{4}-){2}[A-Z0-9]{6}')
LEVELS = [
    '1.1', '1.2', '1.3', '1.4', '1.5', '1.6', '1.7', '1.8', '1.b1',
    '2.1', '2.2', '2.3', '2.4', '2.5', '2.6', '2.7', '2.8', '2.b1',
    '3.1', '3.2', '3.3', '3.4', '3.5', '3.6', '3.7', '3.8', '3.b1',
    '4.1', '4.2', '4.3', '4.4', '4.5', '4.6', '4.7', '4.8', '4.b1',
    '5.1', '5.2', '5.3', '5.4', '5.5', '5.6', '5.7', '5.8', '5.b1', '5.b2',
    '6.1', '6.2', '6.3', '6.4', 'rumble', 'dev', 'zecred',
    'DQ1', 'DQ3', 'DQ4', 'DQ5', 'DQ7', 'DQ8', 'DQ9', 'DQ10', 'DQ11', 'DQ12',
]


class Session:
    def __init__(self, session: aiohttp.ClientSession = None) -> None:
        self._session = session or aiohttp.ClientSession()
        self._cooldown = {'DailyQuestInfo': 0, 'LatestNews': 0, 'DailyQuestLeaderboards': {
        }, 'SkillPointLeaderboard': 0, 'BasicLevelsTopLeaderboards': {}, 'Leaderboards': {}, 'seasonal': 0}
        self._DailyQuestLeaderboards = {}
        self._BasicLevelsTopLeaderboards = {}
        self._Leaderboards = {}

    async def close(self):
        '''Closes the internal ClientSession.'''
        await self._session.close()

    @staticmethod
    def _get_args(method, mapname, mode, difficulty):
        return {'method': method, 'mapname': str(mapname), 'mode': mode, 'difficulty': difficulty}

    @staticmethod
    def _kwarg_check(mapname=None, playerid=None, mode=None, difficulty=None, date=None):
        if mapname and str(mapname) not in LEVELS:
            raise APIError('Invalid map: ' + mapname)
        if playerid and not ID_REGEX.match(playerid):
            raise APIError('Invalid playerid: ' + playerid)
        if mode and not mode in ('score', 'waves'):
            raise APIError("Invalid mode (must be either 'score' or 'waves'): " + mode)  # nopep8
        if difficulty and not difficulty in ('EASY', 'NORMAL', 'ENDLESS_I'):
            raise APIError("Invalid difficulty (must be one of 'EASY', 'NORMAL', 'ENDLESS_I': " + difficulty)  # nopep8

    async def _post(self, arg: str, data: dict = None) -> dict:
        '''Internal post method to communicate with Rainy's API'''
        url = f'https://infinitode.prineside.com/?m=api&a={arg}&apiv=1&g=com.prineside.tdi2&v=282'
        async with self._session.post(url, data=data) as r:
            try:
                r.raise_for_status()
            except aiohttp.ClientResponseError:
                raise APIError("Something went wrong. Try again later")

            data = await r.json()

            if data['status'] == 'success':
                return data
            else:
                raise APIError('Error response from server: ' + data['status'])

    async def leaderboards_rank(self, mapname, playerid, mode='score', difficulty='NORMAL', raw=False) -> Score:
        """|coro|

        Retrieves a Score of the given player.
        A valid playerid needs to be specified.

        Returns
        --------
        Score
            A Score
        """
        self._kwarg_check(mapname=mapname, playerid=playerid, mode=mode, difficulty=difficulty)  # nopep8
        data = await self._post('getLeaderboardsRank', data={'gamemode': 'BASIC_LEVELS', 'difficulty': difficulty, 'playerid': playerid, 'mapname': str(mapname), 'mode': mode})
        if raw:
            return data
        return Score('leaderboards_rank', mapname, mode, difficulty, playerid, **data['player'])

    async def leaderboards(self, mapname, playerid=None, mode='score', difficulty='NORMAL', raw=False) -> Leaderboard:
        """|coro|

        Retrieves a Leaderboard.
        The leaderboard will have a .player attribute if a valid playerid is specified.
        The leaderboard contains the top 200 scores of the specified map.

        Returns
        --------
        Leaderboard
            A Leaderboard
        """
        self._kwarg_check(mapname=mapname, playerid=playerid, mode=mode, difficulty=difficulty)  # nopep8
        key = f'{difficulty}{mode}{mapname}'
        if not raw and not playerid and (time.time() < self._cooldown['Leaderboards'].get(key, 0) + 60):
            return self._Leaderboards[key]
        data = await self._post('getLeaderboards', data={'gamemode': 'BASIC_LEVELS', 'difficulty': difficulty, 'playerid': playerid, 'mapname': str(mapname), 'mode': mode})
        if raw:
            return data
        d = data['player']
        args = self._get_args('leaderboards', mapname, mode, difficulty)
        lb = Leaderboard(**args, total=int(d['total']))
        for r, x in enumerate(data['leaderboards'], start=1):
            lb._append(Score(**args, rank=r, **x))
        if not (d['score'] and d['rank'] and d['total']):
            self._Leaderboards[key] = lb
            self._cooldown['Leaderboards'][key] = time.time()
        else:
            lb._add_player(Score(**args, playerid=playerid, **d))
        return lb

    async def runtime_leaderboards(self, mapname, playerid, mode='score', difficulty='NORMAL', raw=False) -> Leaderboard:
        """|coro|

        Retrieves a Leaderboard.
        The leaderboard will have a .player attribute.
        A valid playerid needs to be specified.
        The leaderboard contains the top 200 scores and one Score for each top% of the specified map.

        Returns
        --------
        Leaderboard
            A Leaderboard
        """
        self._kwarg_check(mapname=mapname, playerid=playerid, mode=mode, difficulty=difficulty)  # nopep8
        data = await self._post('getRuntimeLeaderboards', data={'gamemode': 'BASIC_LEVELS', 'difficulty': difficulty, 'playerid': playerid, 'mapname': str(mapname), 'mode': mode})
        if raw:
            return data
        args = self._get_args('runtime_leaderboards', mapname, mode, difficulty)  # nopep8
        d = data['player']
        lb = Leaderboard(**args, total=int(d['total']))
        for r, x in enumerate(data['leaderboards'], start=1):
            lb._append(Score(**args, rank=r, **x))
        lb._add_player(Score(**args, playerid=playerid, **d))
        return lb

    async def skill_point_leaderboard(self, playerid=None, raw=False) -> Leaderboard:
        """|coro|

        Retrieves a Leaderboard.
        The leaderboard will have a .player attribute if a valid playerid is specified.
        The leaderboard contains the top 3 skill point owners (looking at you, Eupho!).
        The leaderboard's mapname will be 'SP', the mode 'score' and the difficulty 'NORMAL'.

        Returns
        --------
        Leaderboard
            A Leaderboard
        """
        if playerid:
            self._kwarg_check(playerid=playerid)
        elif not raw and not playerid and time.time() < self._cooldown['SkillPointLeaderboard'] + 60:
            return self._SkillPointLeaderboard
        data = await self._post('getSkillPointLeaderboard', data={'playerid': playerid})
        if raw:
            return data
        d = data['player']
        args = self._get_args('skill_point_leaderboard', 'SP', 'score', 'NORMAL')  # nopep8
        lb = Leaderboard(**args, total=int(d['total']))
        for r, x in enumerate(data['leaderboards'], start=1):
            lb._append(Score(**args, rank=r, **x))
        if not (d['score'] and d['rank'] and d['total']):
            self._SkillPointLeaderboard = lb
            self._cooldown['SkillPointLeaderboard'] = time.time()
        else:
            lb._add_player(Score(**args, playerid=playerid, **d))
        return lb

    async def daily_quest_leaderboards(self, date: datetime.datetime = None, playerid=None, warning=True, return_date=False, raw=False) -> Union[Leaderboard, Tuple[Leaderboard, str]]:
        """|coro|

        Retrieves a Leaderboard.
        The leaderboard will have a .player attribute if a valid playerid is specified.
        If an invalid or no date is provided, the date will be set to the current date.
        The Leaderboard will have a .date attribute.
        You may disable the invalid date warning by setting the warning param to False.
        The leaderboard contains the top 200 DQ players of the given date.
        The leaderboard's mapname will be 'DQ', the mode 'score' and the difficulty 'NORMAL'.

        Returns
        --------
        Leaderboard
            A Leaderboard
        """
        if date:
            try:
                date = date.strftime('%Y-%m-%d')
            except:
                try:
                    date = parser.parse(date, ignoretz=True).strftime('%Y-%m-%d')  # nopep8
                except:
                    if warning:
                        print('Warning: Invalid date was passed into daily_quest_leaderboards: ' + date)  # nopep8
                    date = datetime.datetime.utcnow().strftime('%Y-%m-%d')
        else:
            date = datetime.datetime.utcnow().strftime('%Y-%m-%d')
        if not raw and not playerid and (time.time() < self._cooldown['DailyQuestLeaderboards'].get(date, 0) + 60):
            return self._DailyQuestLeaderboards[date]
        data = await self._post('getDailyQuestLeaderboards', data={'date': date, 'playerid': playerid})
        if raw:
            return data
        d = data['player']
        args = self._get_args('daily_quest_leaderboards', 'DQ', 'score', 'NORMAL')  # nopep8
        lb = Leaderboard(**args, date=date, total=int(d['total']))  # nopep8
        for r, x in enumerate(data['leaderboards'], start=1):
            lb._append(Score(**args, rank=r, **x))
        if not (d['score'] and d['rank'] and d['total']):
            self._DailyQuestLeaderboards[date] = lb
            self._cooldown['DailyQuestLeaderboards'][date] = time.time()
        else:
            lb._add_player(Score(**args, playerid=playerid, **d))
        return lb if not return_date else (lb, date)

    async def seasonal_leaderboard(self) -> Leaderboard:
        """|coro|

        Retrieves the season Leaderboard.
        The leaderboard contains the top 100 scores in the season.
        The leaderboard's mapname will be 'season', the mode 'score' and the difficulty 'NORMAL'.

        Returns
        --------
        Leaderboard
            A Leaderboard
        """
        if time.time() < self._cooldown['seasonal'] + 60:
            return self._seasonal
        url = f'https://infinitode.prineside.com/xdx/?url=seasonal_leaderboard'
        r = await self._session.get(url=url)
        try:
            r.raise_for_status()
        except aiohttp.ClientResponseError:
            raise APIError('Bad Gateway')
        seasonal = bs4.BeautifulSoup(await r.text(), 'lxml')
        season = int(seasonal.select_one('label[i18n="season_formatted"]')[
            'i18nf'].replace('["', '').replace('"]', ''))
        player_count = int(seasonal.select('label[i18n="player_count_formatted"]')[
            0]['i18nf'].replace('["', '').replace('"]', '').replace(',', ''))
        args = self._get_args('seasonal_leaderboard', 'season', 'score', 'NORMAL')  # nopep8
        lb = Leaderboard(**args, season=season, total=player_count)
        for x in range(len(seasonal.select('div[x="90"]'))):
            lb._append(Score(**args, rank=x+1,
                             playerid=seasonal.select('label[color="LIGHT_BLUE:P300"]')[
                                 x]['click'].split('id=')[1],
                             nickname=seasonal.select(
                                 'label[color="LIGHT_BLUE:P300"]')[x].text,
                             score=int(seasonal.select(
                                 'label[nowrap="true"][text-align="right"]')[x].text.replace(',', ''))
                             ))
        self._seasonal = lb
        self._cooldown['seasonal'] = time.time()

        return lb

    async def player(self, playerid) -> Player:
        """|coro|

        Retrieves a Player.
        A valid playerid needs to be specified.

        Returns
        --------
        Player
            A Player
        """
        url = f'https://infinitode.prineside.com/xdx/index.php?url=profile/view&id={playerid}'
        r = await self._session.get(url=url)
        try:
            r.raise_for_status()
        except aiohttp.ClientResponseError:
            raise APIError('Bad Gateway')
        data = bs4.BeautifulSoup(await r.text(), 'lxml')
        t = {}
        t['playerid'] = playerid
        t['nickname'] = data.select_one('label:not([i18n])').text
        try:
            t['total_score'] = int(data.select_one(
                'div[width="522"][height="128"][pad-top="10"][pad-bottom="10"][align="center"]').select('label')[1].text.replace(',', ''))
        except:
            t['total_score'] = 0
        try:
            t['total_rank'] = int(data.select_one(
                'div[width="522"][height="128"][pad-top="10"][pad-bottom="10"][align="center"]').select('label')[2].text.replace(',', ''))
        except:
            t['total_rank'] = 0
        try:
            t['total_top'] = data.select_one(
                'div[width="522"][height="128"][pad-top="10"][pad-bottom="10"][align="center"]').select('label')[3].text.replace('- Top ', '')
        except:
            t['total_top'] = 0
        comments = data.findAll(
            text=lambda text: isinstance(text, bs4.Comment))
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
            level = x.select('label')[0].text
            args = {'method': 'player', 'mapname': level, 'mode': 'score',
                    'difficulty': 'NORMAL', 'playerid': playerid}
            t['levels'][level] = Score(
                **args,
                rank=int(x.select('label')[2].text.replace(',', '')),
                score=int(x.select('label')[1].text.replace(',', '')),
                total=int(x.select('label')[3].text.replace(
                    '/ ', '').replace(',', '')),
                top=x.select('label')[-1].text
            ) if not x.select_one('label[i18n="not_ranked"]') else Score(
                **args, rank=0, score=0, total=0, top='-%'
            )
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
        t['created_at'] = datetime.datetime.strptime(
            day + " " + sp[-2] + " " + sp[-1], "%d %B %Y")

        return Player(**t)
