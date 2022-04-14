from datetime import datetime
from dataclasses import dataclass
from typing import List
from typing import Literal
from copy import deepcopy


class APIError(Exception):
    '''API Error'''
    pass


class Badge:
    def __init__(self, iconImg: str, iconColor: str, overlayImg: str, overlayColor: str) -> None:
        self.icon_img = iconImg
        self.icon_color = iconColor
        self.overlay_img = overlayImg
        self.overlay_color = overlayColor


class Score:
    def __init__(self, method, mapname, mode, difficulty, playerid, rank, score,
                 hasPfp=None, level=None, nickname=None, pinnedBadge=None, position=None, top=None, total=None) -> None:
        self.method: Literal['leaderboards_rank', 'leaderboards', 'runtime_leaderboards',
                             'skill_point_leaderboard', 'daily_quest_leaderboards', 'seasonal_leaderboard', 'player'] = method
        self.mapname: str = mapname
        self.mode: Literal['score', 'waves'] = mode
        self.difficulty: Literal['EASY', 'NORMAL', 'ENDLESS_I'] = difficulty
        self.playerid: str = playerid
        self.rank: int = int(rank)
        self.score: int = int(score)
        if hasPfp is not None:
            self.has_pfp: bool = bool(hasPfp)
        if level is not None:
            self.level: int = int(level)
        if nickname is not None:
            self.nickname: str = nickname
        if pinnedBadge is not None:
            self.pinned_badge: Badge = Badge(**pinnedBadge)
        if position is not None:
            self.position: int = int(position)
        if top is not None:
            self.top: str = top
        if total is not None:
            self.total: int = int(total)

    async def fetch_player(self, session):
        '''Fetch the player using a given session (This is an API call).'''
        return await session.player(self.playerid)

    def format_score(self):
        try:
            return '#{:<5} {:<22} {:>0,}'.format(self.rank, self.nickname if len(self.nickname) < 21 else f"{self.nickname[:19]}...", self.score)
        except AttributeError:
            raise APIError('The score is not valid for formatting (most likely there is no nickname attached to this score).')  # nopep8

    def print_score(self):
        print(self.format_score())


class Leaderboard:
    def __init__(self, method, mapname, mode, difficulty, total, date=None, player=None, season=None) -> None:
        self.method: Literal['leaderboards_rank', 'leaderboards', 'runtime_leaderboards',
                             'skill_point_leaderboard', 'daily_quest_leaderboards', 'seasonal_leaderboard', 'player'] = method
        self.mapname: str = mapname
        self.mode: Literal['score', 'waves'] = mode
        self.difficulty: Literal['EASY', 'NORMAL', 'ENDLESS_I'] = difficulty
        self.total: int = int(total)
        if date is not None:
            self.date: datetime = date
        if season is not None:
            self.season: int = int(season)
        if player is not None:
            self.player: Score = player
        self._scores: List[Score] = []

    def format_scores(self):
        '''Default format used in my Advinas Bot. To format the scores yourself, iterate over this object.'''
        return '\n'.join(['#{:<5} {:<22} {:>0,}'.format(i.rank, i.nickname if len(i.nickname) < 21 else f"{i.nickname[:19]}...", i.score) for i in self._scores])

    @property
    def is_empty(self):
        '''Whether there are no scores saved in this leaderboard or there are.'''
        return not self._scores

    def print_scores(self):
        '''Prints out the result of format_scores().'''
        print(self.format_scores())

    def get_score(self, attr, val):
        return next(x for x in self._scores if getattr(x, attr) == val)

    def _add_player(self, score):
        self.player = score

    def _append(self, score):
        '''Internal append method.'''
        self._scores.append(score)

    def __len__(self):
        return len(self._scores)

    def __contains__(self, item):
        return item in self._scores

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._scores[key]
        else:
            kwargs = deepcopy(self.__dict__)
            kwargs.pop('_scores')
            lb = Leaderboard(**kwargs)
            lb._scores = []
            for score in self._scores[key]:
                lb._append(score)
            return lb

    def __iter__(self):
        self._index = 0
        return self

    def __next__(self):
        try:
            score = self._scores[self._index]
        except KeyError:
            raise StopIteration
        self._index += 1
        return score


@dataclass
class Player:
    playerid: str
    nickname: str
    levels: dict
    level: int
    xp: int
    xp_max: int
    badges: dict
    total_score: int
    total_rank: int
    total_top: str
    replays: int
    issues: int
    created_at: datetime

    @property
    def avatar_link(self):
        return f'https://infinitode.prineside.com/img/avatars/{self.playerid}-128.png'

    def score(self, level) -> str:
        try:
            return self.levels[level]
        except KeyError:
            self.levels[level] = Score('player', level, 'score', 'NORMAL', self.playerid, **{'rank': 0, 'score': 0, 'total': 0, 'top': '-%'})  # nopep8
            return self.levels[level]

    async def _get_daily_quest(self, session):
        lb = await session.daily_quest_leaderboards(playerid=self.playerid)
        try:
            self.daily_quest = lb.player
        except:
            self.daily_quest = Score('player', 'DQ', 'score', 'NORMAL', self.playerid, **{'rank': 0, 'score': 0, 'total': 0, 'top': '-%'})  # nopep8
        return self.daily_quest

    async def _get_skill_point(self, session):
        lb = await session.skill_point_leaderboard(playerid=self.playerid)
        try:
            self.skill_point = lb.player
        except:
            self.skill_point = Score('player', 'SP', 'score', 'NORMAL', self.playerid, **{'rank': 0, 'score': 0, 'total': 0, 'top': '-%'})  # nopep8
        return self.skill_point
