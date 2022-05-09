from __future__ import annotations

# std
from typing import (
    Any,
    Dict,
    List,
    Optional,
    TYPE_CHECKING
)
# packages
import discord
from discord.ext import menus
from infinitode import Leaderboard

# locals
from common.custom import Context
from common.utils import codeblock

if TYPE_CHECKING:
    from .views import Paginator, ScorePaginator


class LBSource(menus.ListPageSource):
    def __init__(self, ctx: Context, data: Leaderboard, title: str, headline: Optional[str] = None):
        self.title = title
        self.headline = headline
        self.user = ctx.author
        self.entries: Leaderboard
        super().__init__(data, per_page=20)

    async def format_page(self, menu: Paginator, entries: Leaderboard):
        description = codeblock(
            (f'{self.headline}\n' if self.headline else '') + entries.format_scores())
        return discord.Embed(title=self.title, description=description, colour=60415
                             ).set_footer(text=f"Requested by {self.user}", icon_url=self.user.display_avatar.url)


class ScoreLBSource(LBSource):
    def __init__(self, ctx: Context, data: Leaderboard, endless_data: Leaderboard, title: str):
        super().__init__(ctx, data, title=title)
        self.endless_entries = endless_data

    async def get_page(self, menu: ScorePaginator, page_number: int) -> Leaderboard:
        if not menu.endless:
            entries = self.entries
        else:
            entries = self.endless_entries
        base = page_number * self.per_page
        return entries[base:base + self.per_page]

    async def format_page(self, menu: ScorePaginator, entries: Leaderboard):
        mode = 'Endless' if menu.endless else 'Normal'
        description = codeblock(f'{mode} mode:\n' + entries.format_scores())
        return discord.Embed(title=self.title, description=description, colour=60415
                             ).set_footer(text=f"Requested by {self.user}", icon_url=self.user.display_avatar.url)


class TagSource(menus.ListPageSource):
    def __init__(self, entries: List[Dict[str, Any]], name: str, user):
        self.name = name
        self.user = user
        super().__init__(entries, per_page=20)

    async def format_page(self, menu, page: List[Dict[str, Any]]):
        description = '\n'.join(
            [f"{tag['name']} (Uses: {tag['uses']})" if not tag.get('alias', None) else f"{tag['name']} (Alias to {tag['alias']})" for tag in page])
        return discord.Embed(title=f'Tag list for {self.name}', description=codeblock(description), colour=60415
                             ).set_footer(text=f"Requested by {self.user}", icon_url=self.user.display_avatar.url)
