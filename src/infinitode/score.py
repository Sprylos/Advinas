from __future__ import annotations

# std
from typing import (
    Any,
    Dict,
    Optional,
    Union,
    TYPE_CHECKING
)

# local
from .errors import InfinitodeError
from .badge import Badge

if TYPE_CHECKING:
    from .core import Session
    from .player import Player

__all__ = ('Score',)


class Score:
    '''Represents a single in-game Score.'''
    __slots__ = (
        'method',
        'mapname',
        'mode',
        'difficulty',
        'playerid',
        'rank',
        'score',
        'raw',
        'has_pfp',
        'level',
        'nickname',
        'pinned_badge',
        'position',
        'top',
        'total',
        'player',
    )

    def __init__(
        self,
        method: str,
        mapname: str,
        mode: str,
        difficulty: str,
        playerid: str,
        rank: Union[int, str],
        score: Union[int, str],
        *,
        raw: Dict[str, Any],
        hasPfp: Optional[bool] = None,
        level: Optional[int] = None,
        nickname: Optional[str] = None,
        pinnedBadge: Optional[Dict[str, str]] = None,
        position: Optional[int] = None,
        top: Optional[str] = None,
        total: Optional[Union[str, int]] = None,
        player: Optional[Player] = None
    ) -> None:
        self.method = method
        self.mapname = mapname
        self.mode = mode
        self.difficulty = difficulty
        self.playerid = playerid
        self.rank = int(rank)
        self.score = int(score)
        self.raw = raw
        self.has_pfp = hasPfp
        self.level = level
        self.nickname = nickname
        self.pinned_badge: Optional[Badge] = Badge(**pinnedBadge) if pinnedBadge is not None else None  # nopep8
        self.position: Optional[int] = int(position) if position is not None else None  # nopep8
        self.top = top
        self.total: Optional[int] = int(total) if total is not None else None
        self.player = player

    @classmethod
    def from_payload(
        cls,
        # a standalone score payload is only received from the leaderboards rank call
        method: str,
        mapname: str,
        mode: str,
        difficulty: str,
        playerid: str,
        payload: Dict[str, Any]
    ) -> Score:
        score: Dict[str, Any] = payload['player']
        return cls(method, mapname, mode, difficulty, playerid, **score, raw=payload)

    async def fetch_player(self, session: Session) -> Player:
        '''Fetch the player using a given session (This is an API call).'''
        if self.player is None:
            self.player = await session.player(self.playerid)
        return self.player

    def format_score(self):
        if self.nickname is None:
            raise InfinitodeError('The score is not valid for formatting (There is no nickname attached to this score).')  # nopep8
        return '#{:<5} {:<22} {:>0,}'.format(self.rank, self.nickname if len(self.nickname) < 21 else f"{self.nickname[:19]}...", self.score)

    def print_score(self):
        print(self.format_score())
