import discord
from discord.ext import menus
from common.utils import codeblock


class LBSource(menus.ListPageSource):
    def __init__(self, data, title: str, ctx, headline: str = None):
        self.title = title
        self.headline = headline
        self.ctx = ctx
        super().__init__(data, per_page=20)

    async def format_page(self, menu, entries):
        offset = menu.current_page * self.per_page
        lines = [self.headline] if self.headline else []
        for r, p in enumerate(entries, start=offset):
            lines.append('#{:<5} {:<22} {:>0,}'.format(r+1, p['nickname'] if len(
                p['nickname']) < 21 else f"{p['nickname'][:19]}...", p['score']))
        description = codeblock('\n'.join(lines))
        return discord.Embed(title=self.title, description=description, colour=60415
                             ).set_footer(text=f"Requested by {self.ctx.author}", icon_url=self.ctx.author.avatar.url)


class ScoreLBSource(LBSource):
    def __init__(self, data, endless_data, title: str, ctx):
        super().__init__(data, title=title, ctx=ctx)
        self.endless_entries = endless_data

    async def get_page(self, menu, page_number):
        if not menu.endless:
            entries = self.entries
        else:
            entries = self.endless_entries
        if self.per_page == 1:
            return entries[page_number]
        else:
            base = page_number * self.per_page
            ret = entries[base:base + self.per_page]
            return ret

    async def format_page(self, menu, entries):
        offset = menu.current_page * self.per_page
        mode = 'Endless' if menu.endless else 'Normal'
        lines = [f'{mode} mode:']
        for r, p in enumerate(entries, start=offset):
            lines.append('#{:<5} {:<22} {:>0,}'.format(r+1, p['nickname'] if len(
                p['nickname']) < 21 else f"{p['nickname'][:19]}...", p['score']))
        description = codeblock('\n'.join(lines))
        return discord.Embed(title=self.title, description=description, colour=60415
                             ).set_footer(text=f"Requested by {self.ctx.author}", icon_url=self.ctx.author.avatar.url)
