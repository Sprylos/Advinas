import discord
from discord.ext import menus
from common.utils import codeblock
from infinitode.models import Leaderboard


class LBSource(menus.ListPageSource):
    def __init__(self, data: Leaderboard, title: str, ctx, headline: str = None):
        self.title = title
        self.headline = headline
        self.ctx = ctx
        super().__init__(data, per_page=20)

    async def format_page(self, menu, entries: Leaderboard):
        description = codeblock(
            (f'{self.headline}\n' if self.headline else '') + entries.format_scores())
        return discord.Embed(title=self.title, description=description, colour=60415
                             ).set_footer(text=f"Requested by {self.ctx.author}", icon_url=self.ctx.author.avatar.url)


class ScoreLBSource(LBSource):
    def __init__(self, data: Leaderboard, endless_data: Leaderboard, title: str, ctx):
        super().__init__(data, title=title, ctx=ctx)
        self.endless_entries = endless_data

    async def get_page(self, menu, page_number):
        if not menu.endless:
            entries = self.entries
        else:
            entries = self.endless_entries
        base = page_number * self.per_page
        return entries[base:base + self.per_page]

    async def format_page(self, menu, entries: Leaderboard):
        mode = 'Endless' if menu.endless else 'Normal'
        description = codeblock(f'{mode} mode:\n' + entries.format_scores())
        return discord.Embed(title=self.title, description=description, colour=60415
                             ).set_footer(text=f"Requested by {self.ctx.author}", icon_url=self.ctx.author.avatar.url)
