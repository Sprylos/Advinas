from __future__ import annotations

# std
import re
import time
import datetime

# packages
import aiohttp
import bs4
from dateutil import parser  # type: ignore
from typing import (
    Any,
    Dict,
    Optional,
    Union,
)


# local
from .errors import APIError, BadArgument
from .leaderboard import Leaderboard
from .player import Player
from .score import Score


__all__ = ('Session',)

ID_REGEX = re.compile(r'U-([A-Z0-9]{4}-){2}[A-Z0-9]{6}')
LEVELS = (
    '1.1', '1.2', '1.3', '1.4', '1.5', '1.6', '1.7', '1.8', '1.b1',
    '2.1', '2.2', '2.3', '2.4', '2.5', '2.6', '2.7', '2.8', '2.b1',
    '3.1', '3.2', '3.3', '3.4', '3.5', '3.6', '3.7', '3.8', '3.b1',
    '4.1', '4.2', '4.3', '4.4', '4.5', '4.6', '4.7', '4.8', '4.b1',
    '5.1', '5.2', '5.3', '5.4', '5.5', '5.6', '5.7', '5.8', '5.b1', '5.b2',
    '6.1', '6.2', '6.3', '6.4', 'rumble', 'dev', 'zecred',
    'DQ1', 'DQ3', 'DQ4', 'DQ5', 'DQ7', 'DQ8', 'DQ9', 'DQ10', 'DQ11', 'DQ12',
)


class Session:
    def __init__(self, session: Optional[aiohttp.ClientSession] = None) -> None:
        self._session = session or aiohttp.ClientSession()
        self._cooldown: Dict[str, Any] = {'DailyQuestInfo': 0.0, 'LatestNews': 0.0, 'DailyQuestLeaderboards': {
        }, 'SkillPointLeaderboard': 0.0, 'BasicLevelsTopLeaderboards': {}, 'Leaderboards': {}, 'seasonal': 0.0}
        self._DailyQuestLeaderboards: Dict[str, Leaderboard] = {}
        self._BasicLevelsTopLeaderboards: Dict[str, Leaderboard] = {}
        self._Leaderboards: Dict[str, Leaderboard] = {}
        self._SkillPointLeaderboard: Leaderboard
        self._seasonal: Leaderboard

    async def close(self):
        '''Closes the internal ClientSession.'''
        await self._session.close()

    @staticmethod
    def _get_args(method: str, mapname: Any, mode: str, difficulty: str) -> Dict[str, Any]:
        return {'method': method, 'mapname': str(mapname), 'mode': mode, 'difficulty': difficulty}

    @staticmethod
    def _kwarg_check(mapname: Optional[str] = None, playerid: Optional[str] = None, mode: Optional[str] = None, difficulty: Optional[str] = None) -> None:
        if mapname and str(mapname) not in LEVELS:
            raise BadArgument('Invalid map: ' + mapname)
        if playerid and not ID_REGEX.match(playerid):
            raise BadArgument('Invalid playerid: ' + playerid)
        if mode and not mode in ('score', 'waves'):
            raise BadArgument("Invalid mode (must be either 'score' or 'waves'): " + mode)  # nopep8
        if difficulty and not difficulty in ('EASY', 'NORMAL', 'ENDLESS_I'):
            raise BadArgument("Invalid difficulty (must be one of 'EASY', 'NORMAL', 'ENDLESS_I': " + difficulty)  # nopep8

    async def _post(self, arg: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        '''Internal post method to communicate with Rainy's API'''
        url = f'https://infinitode.prineside.com/?m=api&a={arg}&apiv=1&g=com.prineside.tdi2&v=282'
        async with self._session.post(url, data=data) as r:
            try:
                r.raise_for_status()
            except aiohttp.ClientResponseError:
                raise APIError("Something went wrong. Try again later")

            payload: Dict[str, Any] = await r.json()

            if payload['status'] == 'success':
                return payload
            else:
                raise APIError(f'Error response from server: {payload["status"]}')  # nopep8

    async def leaderboards_rank(self, mapname: Any, playerid: str, mode: str = 'score', difficulty: str = 'NORMAL') -> Score:
        """|coro|

        Retrieves a Score of the given player.
        A valid playerid needs to be specified.

        Returns
        --------
        Score
            A Score
        """
        self._kwarg_check(mapname=mapname, playerid=playerid, mode=mode, difficulty=difficulty)  # nopep8
        payload = await self._post('getLeaderboardsRank', data={'gamemode': 'BASIC_LEVELS', 'difficulty': difficulty, 'playerid': playerid, 'mapname': str(mapname), 'mode': mode})
        return Score.from_payload('leaderboards_rank', mapname, mode, difficulty, playerid, payload)

    async def leaderboards(self, mapname: Any, playerid: Optional[str] = None, mode: str = 'score', difficulty: str = 'NORMAL') -> Leaderboard:
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
        if not playerid and (time.time() < self._cooldown['Leaderboards'].get(key, 0) + 60):
            return self._Leaderboards[key]
        payload = await self._post('getLeaderboards', data={'gamemode': 'BASIC_LEVELS', 'difficulty': difficulty, 'playerid': playerid, 'mapname': str(mapname), 'mode': mode})
        lb = Leaderboard.from_payload('leaderboards', mapname, mode, difficulty, playerid, payload)  # nopep8
        if lb.player is None:
            self._Leaderboards[key] = lb
            self._cooldown['Leaderboards'][key] = time.time()
        return lb

    async def runtime_leaderboards(self, mapname: Any, playerid: str, mode: str = 'score', difficulty: str = 'NORMAL') -> Leaderboard:
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
        payload = await self._post('getRuntimeLeaderboards', data={'gamemode': 'BASIC_LEVELS', 'difficulty': difficulty, 'playerid': playerid, 'mapname': str(mapname), 'mode': mode})
        return Leaderboard.from_payload('runtime_leaderboards', mapname, mode, difficulty, playerid, payload)

    async def skill_point_leaderboard(self, playerid: Optional[str] = None) -> Leaderboard:
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
        if playerid is not None:
            self._kwarg_check(playerid=playerid)
        elif time.time() < self._cooldown['SkillPointLeaderboard'] + 60:
            return self._SkillPointLeaderboard
        payload = await self._post('getSkillPointLeaderboard', data={'playerid': playerid})
        lb = Leaderboard.from_payload('skill_point_leaderboard', 'SP', 'score', 'NORMAL', playerid, payload)  # nopep8
        if lb.player is None:
            self._SkillPointLeaderboard = lb
            self._cooldown['SkillPointLeaderboard'] = time.time()
        return lb

    async def daily_quest_leaderboards(
        self,
        date: Union[datetime.datetime, str, None] = None,
        playerid: Optional[str] = None,
        warning: bool = True,
    ) -> Leaderboard:
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
        if date is not None:
            if isinstance(date, datetime.datetime):
                date = date.strftime('%Y-%m-%d')
            else:
                try:
                    date = parser.parse(date, ignoretz=True).strftime('%Y-%m-%d')  # nopep8
                except (parser.ParserError, OverflowError):
                    if warning == True:
                        print(f'Warning: Invalid date was passed into daily_quest_leaderboards: {date}')  # nopep8
                    date = datetime.datetime.utcnow().strftime('%Y-%m-%d')
        else:
            date = datetime.datetime.utcnow().strftime('%Y-%m-%d')
        if not playerid and (time.time() < self._cooldown['DailyQuestLeaderboards'].get(date, 0) + 60):
            return self._DailyQuestLeaderboards[date]  # type: ignore # date is always a str here # nopep8
        payload = await self._post('getDailyQuestLeaderboards', data={'date': date, 'playerid': playerid})
        lb = Leaderboard.from_payload('daily_quest_leaderboards', 'DQ', 'score', 'NORMAL', playerid, payload)  # nopep8
        if lb.player is None:
            self._DailyQuestLeaderboards[date] = lb  # type: ignore # date is always a str here # nopep8
            self._cooldown['DailyQuestLeaderboards'][date] = time.time()
        return lb

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
        r = await self._session.get(url='https://infinitode.prineside.com/xdx/?url=seasonal_leaderboard')
        try:
            r.raise_for_status()
        except aiohttp.ClientResponseError:
            raise APIError('Bad Gateway.')
        seasonal = bs4.BeautifulSoup(await r.text(), 'lxml')
        season = int(seasonal.select_one('label[i18n="season_formatted"]')['i18nf'].replace('["', '').replace('"]', ''))  # type: ignore # nopep8
        player_count = int(seasonal.select('label[i18n="player_count_formatted"]')[  # type: ignore
            0]['i18nf'].replace('["', '').replace('"]', '').replace(',', ''))  # type: ignore
        lb = Leaderboard.from_payload(
            'seasonal_leaderboard', 'season', 'score', 'NORMAL', None, {
                'status': 'success',
                'player': {'total': player_count},
                'leaderboards': [
                    {
                        'playerid': seasonal.select('label[color="LIGHT_BLUE:P300"]')[x]['click'].split('id=')[1],  # type: ignore # nopep8
                        'nickname': seasonal.select('label[color="LIGHT_BLUE:P300"]')[x].text,  # type: ignore # nopep8
                        'score': seasonal.select('label[nowrap="true"][text-align="right"]')[x].text.replace(',', '')  # type: ignore # nopep8
                    } for x in range(len(seasonal.select('div[x="90"]')))  # type: ignore
                ]
            }, season=season
        )
        self._seasonal = lb
        self._cooldown['seasonal'] = time.time()
        return lb

    async def player(self, playerid: str) -> Player:
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
            raise APIError('Bad Gateway.')
        data = bs4.BeautifulSoup(await r.text(), 'lxml')
        t: Dict[str, Any] = {}
        t['playerid'] = playerid
        t['nickname'] = data.select_one('label:not([i18n])').text  # type: ignore # this should never fail # nopep8
        if (totals := data.select_one('div[width="522"][height="128"][pad-top="10"][pad-bottom="10"][align="center"]')) is not None:  # type: ignore # nopep8
            totals = totals.select('label')  # type: ignore # nopep8
            try:
                t['total_score'] = int(totals[1].text.replace(',', ''))
            except (KeyError, ValueError):
                t['total_score'] = 0
            try:
                t['total_rank'] = int(totals[2].text.replace(',', ''))
            except (KeyError, ValueError):
                t['total_rank'] = 0
            try:
                t['total_top'] = totals[3].text.replace('- Top ', '')
            except (KeyError, ValueError):
                t['total_top'] = 0
        else:
            t.update({'total_score': 0, 'total_rank': 0, 'total_top': 0})
        comments = data.findAll(
            text=lambda text: isinstance(text, bs4.Comment))
        for x in comments:
            if 'Level:' in x:
                t['level'] = int(x.split('>')[3].split('<')[0])
                break
        xp_data = data.select_one('div[width="330"][height="64"]').select_one('label').text.split(' / ')  # type: ignore # nopep8
        t['xp'] = int(xp_data[0])
        t['xp_max'] = int(xp_data[1])
        t['levels'] = {}
        for x in data.select('div[width="800"][height="40"]')[1:]:  # type: ignore # nopep8
            level_data = x.select('label')  # type: ignore
            level = level_data[0].text
            if not x.select_one('label[i18n="not_ranked"]'):  # type: ignore # nopep8
                rank = int(level_data[2].text.replace(',', ''))
                score = int(level_data[1].text.replace(',', ''))
                total = int(level_data[3].text.replace('/ ', '').replace(',', ''))  # nopep8
                top = level_data[-1].text
            else:
                rank, score, total, top = 0, 0, 0, '-%'
            t['levels'][level] = Score(
                'player', level, 'score', 'NORMAL', playerid, raw={},
                rank=rank, score=score, total=total, top=top,
                level=t['level'], nickname=t['nickname']
            )
        t['badges'] = {}
        for x in data.select('div[width="80"][height="80"]'):  # type: ignore # nopep8
            rar: str = x.select('img')[0]['src'].split('bg-')[1]  # type: ignore # nopep8
            if rar in ['not-received', 'common', 'rare', 'very-rare', 'epic', 'legendary', 'supreme', 'artifact']:
                ico: str = x.select('img')[1]['src'].split('icon-')[1]  # type: ignore # nopep8
                if ico in ['daily-game', 'invited-players', 'killed-enemies', 'mined-resources', 'of-merit', 'beta-tester-season-2'] or ico[:8] == 'season-1':
                    col: str = x.select('img')[-1]['color']  # type: ignore # nopep8
                    t['badges'][ico] = (rar, col)
        labels = data.select('table[width="800"][align="center"]')[-1].select('label')  # type: ignore # nopep8
        t['replays'] = int(labels[-3].string.split(" ")[3])  # type: ignore
        t['issues'] = int(labels[-2].string.split(" ")[0][3:])  # type: ignore
        sp = list(labels[-1].string.split("ned ")[1].split(" "))  # type: ignore # nopep8
        day = sp[0][:-2] if len(sp[0][:2]) == 2 else "0" + sp[0][:2]
        t['created_at'] = datetime.datetime.strptime(
            day + " " + sp[-2] + " " + sp[-1], "%d %B %Y")

        return Player(**t)
