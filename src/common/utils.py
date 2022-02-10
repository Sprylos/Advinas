import json
import traceback
from discord import Color, Embed
from discord.ext.commands.errors import BadArgument, CheckFailure
from math import floor, ceil
from typing import Tuple


class BadLevel(BadArgument):
    """Exception raised when the provided level is not valid."""
    pass


class BadChannel(CheckFailure):
    """Exception raised when the message channel is not an allowed channel."""
    pass


async def answer(ctx, **kwargs):
    '''Replies to users message or just sends it if not possible (in a slash command).'''
    try:
        return await ctx.reply(**kwargs, mention_author=False)
    except:
        # There is a bug that the first response to an interaction can't cointain a file,
        # so we need to avoid that
        if 'file' in kwargs.keys():
            if not ctx.interaction.response.is_done():
                ctx.defer()
        return await ctx.send(**kwargs)


async def log(ctx, success: bool = True, reason: str = None):
    '''Logs the usage of commands. Should be called at the end of any command.'''

    # avoid problems with inconsistencies
    try:
        command = ctx.command.name.lower()
    except AttributeError:
        command = ctx.command.lower()
    try:
        # this works for normal Context objects
        args = ctx.args[2:]
        if args and args[0] != None:
            content = ' '.join(args)
        else:
            content = ''
    except AttributeError:
        # in case of a slash command
        data = ctx.interaction.data
        try:
            options = data['options']
        except KeyError:
            # there were no options (e.g. /profile)
            content = ''
        else:
            # put all inputs into our string
            content = ' '.join([str(option['value']) for option in options])
    value = f'`/{command.lower()}` `{content}`' if content else f'`/{command.lower()}`'

    color = Color.green() if success else Color.red()

    em = Embed(
        title=f"**{command.title()} Command** used in `{ctx.channel}`", colour=color
    ).set_footer(
        text=f"Command run by {ctx.author}",
        icon_url=ctx.author.avatar.url
    ).add_field(
        name='**Success**',
        value=f'`{success}`',
        inline=False
    ).add_field(
        name='**Arguments**',
        value=value,
        inline=False
    )
    if reason:
        em.add_field(
            name='**Reason**',
            value=f'`{reason}`',
            inline=False
        )
    await ctx.bot._log.send(embed=em)


async def trace(ctx, err: Exception):
    '''Called when an unhandled Exception occurs to inform me about the issue.'''
    try:
        # this works for normal Context objects
        args = ctx.args[2:]
        if args and args[0] != None:
            content = ' '.join(args)
        else:
            content = ''
    except AttributeError:
        # in case of a slash command
        data = ctx.interaction.data
        try:
            options = data['options']
        except KeyError:
            # there were no options (e.g. /profile)
            content = ''
        else:
            # put all inputs into our string
            content = ' '.join([str(option['value']) for option in options])
    try:
        command = ctx.command.name.lower()
    except AttributeError:
        command = ctx.command.lower()
    tb = f'``' + ' '.join(['Error occured in command', command, '\n']) + ''.join(
        traceback.format_exception(type(err), err, err.__traceback__)) + '``'
    if len(tb) > 1020:
        await ctx.bot._trace.send(tb)
        tb = tb[:1015] + '...\n``'
    em = Embed(
        title=f"**{command.title()} Command** used in `{ctx.channel}`", colour=Color.red()
    ).set_footer(
        text=f"Command run by {ctx.author}",
        icon_url=ctx.author.avatar.url
    ).add_field(
        name='**Content**',
        value=f'`/{command}` `{content}`' if content else f'`/{command}`',
        inline=False
    ).add_field(
        name='**Traceback**',
        value=tb,
        inline=False
    )
    await ctx.bot._trace.send(embed=em)


def load_json(filename):
    with open(filename, encoding='utf-8') as infile:
        return json.load(infile)


def write_json(filename, contents):
    with open(filename, 'w') as outfile:
        json.dump(contents, outfile, ensure_ascii=True, indent=4)


def codeblock(instring: str) -> str:
    return '```\n' + instring + '```'


def tablify(indict: dict) -> str:
    keys, vals = list(indict.keys()), list(indict.values())
    return '\n'.join([f'{key} {vals[keys.index(key)]}' for key in keys])


def get_level(levels: list, level: str) -> str:
    try:
        level = level.replace('_', '.').replace(
            ',', '.').replace('-', '.').replace(' ', '.').lower()
        assert level in levels
        if level.startswith('dq'):
            level = level.upper()
        return level
    except AssertionError:
        raise BadLevel("Invalid level provided.")


def get_level_bounty(level_diffs: list, level: str, difficulty: float, bounties: int, coins: int) -> Tuple[str, float, int, int]:

    if coins < 50:
        coins = 50
    elif coins > 200:
        coins = 200
    if difficulty < 100:
        difficulty = 100
    elif difficulty > 4500:
        difficulty = 4500
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
