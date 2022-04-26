# std
import json
from math import floor, ceil
from typing import Any, Dict, Optional, Tuple


def codeblock(instring: str) -> str:
    return '```\n' + instring + '```'


def load_json(filename: Any):
    with open(filename, encoding='utf-8') as infile:
        return json.load(infile)


def write_json(filename: Any, contents: Any):
    with open(filename, 'w') as outfile:
        json.dump(contents, outfile, ensure_ascii=True, indent=4)


def tablify(indict: Dict[Any, Any]) -> str:
    keys, vals = list(indict.keys()), list(indict.values())
    return '\n'.join([f'{key} {vals[keys.index(key)]}' for key in keys])


def get_level_bounty(level_diffs: Any, level: Optional[str], difficulty: float, bounties: int, coins: int) -> Tuple[str, float, int, int]:

    if coins < 50:
        coins = 50
    elif coins > 200:
        coins = 200
    if difficulty < 100:
        difficulty = 100
    elif difficulty > 4500:
        difficulty = 4500
    if bounties > 12:
        bounties = 12
    elif bounties < 1:
        bounties = 1
    if not level:
        return 'No level provided', difficulty, bounties, coins
    try:
        _level = level.replace('_', '.').replace(
            ',', '.').replace('-', '.').replace(' ', '.').lower()
        _difficulty: float = level_diffs[level]
        _bounties, _coins = bounties, coins
        if level == 'dq3':
            _bounties, _coins = 10, 50
        elif level == 'dq4':
            _bounties, _coins = 10, 200
        elif level == 'dq8':
            _bounties, _coins = 3, 50
        elif level == 'rumble':
            _bounties = 3
        if _level.startswith('dq'):
            _level = _level.upper()
        return _level, _difficulty, _bounties, _coins
    except KeyError:
        return 'Invalid Level', difficulty, bounties, coins


def round_to_nearest(n: int, m: int) -> int:
    '''Rounds the integer n to the nearest integer divisible by m.'''
    r = n % m
    return n + m - r if r + r >= m else n - r


def find_safe(i: int, buy: int, cost: int, coins: int) -> int:
    '''Find safe buy for bounties after Eupho's algorithm.'''
    d = {0: buy}
    for g in range(5):
        if d[g] == 0:
            return d[g]
        else:
            if (d[g] / 50) > coins:
                if floor((d[g]-cost) / 50) * i >= (coins * (i-1)):
                    return d[g]
                else:
                    d[g+1] = d[g] + 50
            else:
                if floor((d[g]-cost) / 50) * i >= (ceil(d[g] / 50) * (i-1)):
                    return d[g]
                else:
                    d[g+1] = d[g] + 50
    return d[4]
