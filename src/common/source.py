from __future__ import annotations

# std
from typing import List, TYPE_CHECKING

# packages
import wavelink
import discord
from discord.ext import menus
from infinitode import Leaderboard

# locals
from common.custom import Context, Tag, TagAlias
from common.utils import codeblock

if TYPE_CHECKING:
    from .views import Paginator, ScorePaginator


class LBSource(menus.ListPageSource):
    def __init__(
        self, ctx: Context, data: Leaderboard, title: str, headline: str | None = None
    ):
        self.title = title
        self.headline = headline
        self.user = ctx.author
        self.entries: Leaderboard
        super().__init__(data, per_page=20)

    async def format_page(self, menu: Paginator, page: Leaderboard):
        description = codeblock(
            (f"{self.headline}\n" if self.headline else "") + page.format_scores()
        )
        return discord.Embed(
            title=self.title, description=description, colour=60415
        ).set_footer(
            text=f"Requested by {self.user}", icon_url=self.user.display_avatar.url
        )


class ScoreLBSource(LBSource):
    def __init__(
        self, ctx: Context, data: Leaderboard, endless_data: Leaderboard, title: str
    ):
        super().__init__(ctx, data, title=title)
        self.endless_entries = endless_data

    async def get_page(self, menu: ScorePaginator, page_number: int) -> Leaderboard:
        if not menu.endless:
            entries = self.entries
        else:
            entries = self.endless_entries
        base = page_number * self.per_page
        return entries[base : base + self.per_page]

    async def format_page(self, menu: ScorePaginator, page: Leaderboard):
        mode = "Endless" if menu.endless else "Normal"
        description = codeblock(f"{mode} mode:\n" + page.format_scores())
        return discord.Embed(
            title=self.title, description=description, colour=60415
        ).set_footer(
            text=f"Requested by {self.user}", icon_url=self.user.display_avatar.url
        )


class TagSource(menus.ListPageSource):
    def __init__(
        self,
        entries: list[Tag | TagAlias],
        name: str,
        user: discord.User | discord.Member,
    ):
        self.name = name
        self.user = user
        self.alphabetical_sorted: bool = True
        super().__init__(entries, per_page=20)
        self.entries: list[Tag | TagAlias]

    def swap_sorting(self):
        self.alphabetical_sorted = not self.alphabetical_sorted
        if self.alphabetical_sorted:
            self.entries.sort(key=lambda t: t.name)
        else:
            self.entries.sort(key=lambda t: getattr(t, "uses", -1), reverse=True)

    async def format_page(self, menu: Paginator, page: list[Tag | TagAlias]):
        description = "\n".join(
            [
                f"{tag.name} (Uses: {tag.uses})"
                if not isinstance(tag, TagAlias)
                else f'{tag.name} (Alias to "{tag.alias}")'
                for tag in page
            ]
        )
        return discord.Embed(
            title=f"Tag list for {self.name}",
            description=codeblock(description),
            colour=60415,
        ).set_footer(
            text=f"Requested by {self.user}", icon_url=self.user.display_avatar.url
        )


class QueueSource(menus.ListPageSource):
    def __init__(
        self, entries: List[wavelink.Playable], user: discord.User | discord.Member
    ):
        self.user = user
        super().__init__(entries, per_page=15)

    async def format_page(self, menu: Paginator, page: List[wavelink.Playable]):
        description = "\n".join(
            [
                f"{menu.current_page * 15 + c}. [{track.title}]({track.uri}) by {track.author}"
                for c, track in enumerate(page, start=1)
            ]
        )
        return discord.Embed(
            title="Queue", description=description, colour=60415
        ).set_footer(
            text=f"Requested by {self.user}", icon_url=self.user.display_avatar.url
        )
