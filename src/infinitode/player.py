from __future__ import annotations

# std
import datetime
from typing import (
    Any,
    Dict,
    Union,
    Tuple,
    TYPE_CHECKING
)

# local
from .score import Score

if TYPE_CHECKING:
    from .core import Session


__all__ = ('Player',)


class Player:
    '''Represents an in-game Player.'''
    __slots__ = (
        'playerid',
        'nickname',
        'levels',
        'level',
        'xp',
        'xp_max',
        'badges',
        'total_score',
        'total_rank',
        'total_top',
        'replays',
        'issues',
        'created_at',
        'raw',

        'daily_quest',
        'skill_point'
    )

    def __init__(
        self,
        playerid: str,
        nickname: str,
        *,
        levels: Dict[str, Score],
        level: int,
        xp: int,
        xp_max: int,
        badges: Dict[str, Tuple[str, str]],
        total_score: Union[int, str],
        total_rank: Union[int, str],
        total_top: str,
        replays: int,
        issues: int,
        created_at: datetime.datetime,
        raw: Dict[str, Any]
    ) -> None:
        self.playerid = playerid
        self.nickname = nickname
        self.levels = levels
        self.level = level
        self.xp = xp
        self.xp_max = xp_max
        self.badges = badges
        self.total_score = int(total_score)
        self.total_rank = int(total_rank)
        self.total_top = total_top
        self.replays = replays
        self.issues = issues
        self.created_at = created_at
        self.raw = raw

    @property
    def avatar_link(self):
        return f'https://infinitode.prineside.com/img/avatars/{self.playerid}-128.png'

    def score(self, level: str) -> Score:
        try:
            return self.levels[level]
        except KeyError:
            self.levels[level] = Score(
                'player', level, 'score', 'NORMAL', self.playerid,
                rank=0, score=0, total=0, top='-%', raw=self.raw)
            return self.levels[level]

    async def get_daily_quest(self, session: Session) -> Score:
        try:
            return self.daily_quest
        except AttributeError:
            dq_score = (await session.daily_quest_leaderboards(playerid=self.playerid)).player
            if dq_score is None:
                dq_score = Score('player', 'DQ', 'score', 'NORMAL', self.playerid,
                                 rank=0, score=0, total=0, top='-%', raw={})
            self.daily_quest: Score = dq_score
            return dq_score

    async def get_skill_point(self, session: Session) -> Score:
        try:
            return self.skill_point
        except AttributeError:
            sp_score = (await session.skill_point_leaderboard(playerid=self.playerid)).player
            if sp_score is None:
                sp_score = Score('player', 'SP', 'score', 'NORMAL', self.playerid,
                                 rank=0, score=0, total=0, top='-%', raw={})
            self.skill_point: Score = sp_score
            return sp_score
