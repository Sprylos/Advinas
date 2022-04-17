from __future__ import annotations

# std
from copy import deepcopy
from typing import (
    Any,
    Dict,
    List,
    Optional,
    overload,
    Union
)

# local
from .score import Score


__all__ = ('Leaderboard',)


class Leaderboard_iterator:
    '''Iterator class for a leaderboard.'''
    __slots__ = (
        '_scores',
        '_index'
    )

    def __init__(self, scores: List[Score]) -> None:
        self._scores = scores
        self._index: int = 0

    def __next__(self) -> Score:
        try:
            score: Score = self._scores[self._index]
        except KeyError:
            raise StopIteration
        self._index += 1
        return score


class Leaderboard:
    '''Represents an in-game leaderboard.'''
    __slots__ = (
        'method',
        'mapname',
        'mode',
        'difficulty',
        'total',
        'raw',
        'date',
        'season',
        'player',

        '_scores',
    )

    def __init__(
        self,
        method: str,
        mapname: str,
        mode: str,
        difficulty: str,
        total: Union[int, str],
        *,
        raw: Dict[str, Any],
        date: Optional[str] = None,
        player: Optional[Score] = None,
        season: Optional[int] = None
    ) -> None:
        self.method = method
        self.mapname = mapname
        self.mode = mode
        self.difficulty = difficulty
        self.total = int(total)
        self.raw = raw
        self.date = date
        self.season = int(season) if season is not None else None
        self.player = player
        self._scores: List[Score] = []

    @classmethod
    def from_payload(
        cls,
        method: str,
        mapname: str,
        mode: str,
        difficulty: str,
        playerid: Optional[str],
        payload: Dict[str, Any],
        *,
        date: Optional[str] = None,
        season: Optional[int] = None
    ) -> Leaderboard:
        player: Dict[str, Any] = payload['player']
        total: int = player['total']
        if playerid is not None and not (player['score'] and player['rank'] and total):
            player_score = Score(method, mapname, mode, difficulty, playerid, **player, raw=player)  # nopep8
        else:
            player_score = None
        instance = cls(method, mapname, mode, difficulty, total,
                       raw=payload, date=date, player=player_score, season=season)
        for rank, score in enumerate(payload['leaderboards'], start=1):
            instance._append(Score(method, mapname, mode, difficulty, rank=rank, **score, raw=payload))  # nopep8
        return instance

    def format_scores(self) -> str:
        '''Default format used in my Advinas Bot. To format the scores yourself, iterate over this object.'''
        return '\n'.join([i.format_score() for i in self._scores])

    @property
    def is_empty(self) -> bool:
        '''Whether there are no scores saved in this leaderboard or there are.'''
        return not self._scores

    def print_scores(self) -> None:
        '''Prints out the result of format_scores().'''
        print(self.format_scores())

    def get_score(self, attr: str, val: Any) -> Optional[Score]:
        return next((x for x in self._scores if getattr(x, attr) == val), None)

    def _append(self, score: Score) -> None:
        '''Internal append method.'''
        self._scores.append(score)
        self.__getitem__

    # magic methods

    def __len__(self) -> int:
        return len(self._scores)

    def __contains__(self, item: Any) -> bool:
        return item in self._scores

    # this is really not important to do,
    # but i enjoy it.

    @overload
    def __getitem__(self, key: int) -> Score:
        ...

    @overload
    def __getitem__(self, key: slice) -> Leaderboard:
        ...

    def __getitem__(self, key: Any) -> Union[Score, Leaderboard]:
        if isinstance(key, int):
            return self._scores[key]
        elif isinstance(key, slice):
            kwargs = deepcopy(self.__dict__)
            kwargs.pop('_scores')
            lb = Leaderboard(**kwargs)
            lb._scores = []
            for score in self._scores[key]:
                lb._append(score)
            return lb
        else:
            raise KeyError

    def __iter__(self) -> Leaderboard_iterator:
        return Leaderboard_iterator(self._scores)
