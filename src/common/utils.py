from __future__ import annotations

# std
import json
from math import floor, ceil
from typing import Any, Iterable

# packages
from discord import app_commands


def codeblock(instring: str, /, language: str = "") -> str:
    return f"```{language}\n{instring}```"


def load_json(filename: Any):
    with open(filename, encoding="utf-8") as infile:
        return json.load(infile)


def write_json(filename: Any, contents: Any):
    with open(filename, "w") as outfile:
        json.dump(contents, outfile, ensure_ascii=True, indent=4)


def create_choices(iterable: Iterable[str]) -> list[app_commands.Choice[str]]:
    return [app_commands.Choice(name=i, value=i) for i in sorted(iterable)][:25]


def tablify(indict: dict[Any, Any]) -> str:
    keys, vals = list(indict.keys()), list(indict.values())
    return "\n".join([f"{key} {vals[keys.index(key)]}" for key in keys])


def convert_ms(ms: int) -> str:
    """Converts miliseconds to a better readable time format."""
    s = ms // 1000
    if s < 0:
        return "0:00"
    m = int(s // 60)
    s = int(s % 60)
    return f"{m}:{s:02d}"


def convert_ms_literal(ms: int) -> str:
    """Converts miliseconds to a better readable time format."""
    s = ms // 1000
    if s < 0:
        return "0h 00m 00s"
    h = s // 3600
    m = (s // 60) % 60
    s = s % 60
    return f"{h}h {m}m {s}s"


def get_level_bounty(
    level_diffs: dict[str, int | float],
    level: str | None,
    difficulty: int | float,
    bounties: int,
    coins: int,
) -> tuple[str, float, int, int]:
    if level is not None:
        level = (
            level.replace("_", ".")
            .replace(",", ".")
            .replace("-", ".")
            .replace(" ", ".")
            .lower()
        )
        try:
            difficulty = level_diffs[level]
        except KeyError:
            level = "Invalid Level"
        else:
            if level.startswith("dq"):
                level = level.upper()
                coins = 50
                bounties = 5

                if level == "DQ3":
                    bounties = 10
                elif level == "DQ4":
                    bounties, coins = 10, 200
                elif level == "DQ8":
                    bounties = 3

            elif level == "rumble":
                bounties = 3
    else:
        level = "No level provided"

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

    return level, difficulty, bounties, coins


def round_to_nearest(n: int, m: int) -> int:
    """Rounds the integer n to the nearest integer divisible by m."""
    r = n % m
    return n + m - r if r + r >= m else n - r


def find_safe(i: int, buy: int, cost: int, coins: int) -> int:
    """Find safe buy for bounties after Eupho's algorithm."""
    d = {0: buy}
    for g in range(5):
        if d[g] == 0:
            return d[g]
        else:
            if (d[g] / 50) > coins:
                if floor((d[g] - cost) / 50) * i >= (coins * (i - 1)):
                    return d[g]
                else:
                    d[g + 1] = d[g] + 50
            else:
                if floor((d[g] - cost) / 50) * i >= (ceil(d[g] / 50) * (i - 1)):
                    return d[g]
                else:
                    d[g + 1] = d[g] + 50
    return d[4]
