from discord import ButtonStyle, Interaction, ui
from discord.ext import menus
from common.source import LBSource, ScoreLBSource
from common.utils import answer
from typing import Union


class _Paginator(ui.View, menus.MenuPages):
    def __init__(self, source: Union[LBSource, ScoreLBSource], *, delete_message_after=False):
        super().__init__(timeout=60)
        self._source = source
        self.current_page = 0
        self.delete_message_after = delete_message_after

    async def start(self, ctx, *, channel=None, wait=False):
        await self._source._prepare_once()
        self.ctx = ctx
        page = await self._source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        self.message = await ctx.send(**kwargs)

    async def _get_kwargs_from_page(self, page):
        value = await super()._get_kwargs_from_page(page)
        if 'view' not in value:
            value.update({'view': self})
        return value

    async def interaction_check(self, interaction: Interaction):
        """Only allow the author that invoked the command to be able to use the interaction."""
        if interaction.user == self.ctx.author:
            return True
        else:
            await interaction.response.send_message('This is not your interaction!', ephemeral=True)
            return False

    async def on_timeout(self) -> None:
        for button in self.children:
            button.disabled = True
        await self.show_current_page()


class Paginator(_Paginator):
    def __init__(self, source: Union[LBSource, ScoreLBSource], *, delete_message_after=False):
        super().__init__(source, delete_message_after=delete_message_after)

    @ui.button(emoji='<:leftmost:935926623230910535>', style=ButtonStyle.gray)
    async def first_page(self, button, interaction):
        await self.show_page(0)

    @ui.button(emoji='<:left:893612797743759431>', style=ButtonStyle.gray)
    async def before_page(self, button, interaction):
        await self.show_checked_page(self.current_page - 1)

    @ui.button(emoji='<:right:893612798242856962>', style=ButtonStyle.gray)
    async def next_page(self, button, interaction):
        await self.show_checked_page(self.current_page + 1)

    @ui.button(emoji='<:rightmost:935926623591612506>', style=ButtonStyle.gray)
    async def last_page(self, button, interaction):
        await self.show_page(self._source.get_max_pages() - 1)


class ScorePaginator(_Paginator):
    def __init__(self, source: LBSource, *, delete_message_after=False):
        super().__init__(source=source)
        self.endless: bool = False

    async def start(self, ctx, *, channel=None, wait=False):
        await self._source._prepare_once()
        self.ctx = ctx
        page = await self._source.get_page(self, 0)
        kwargs = await self._get_kwargs_from_page(page)
        self.message = await answer(ctx, **kwargs)

    async def show_page(self, page_number):
        page = await self._source.get_page(self, page_number)
        self.current_page = page_number
        kwargs = await self._get_kwargs_from_page(page)
        await self.message.edit(**kwargs)

    @ui.button(emoji='<:leftmost:935926623230910535>', style=ButtonStyle.gray)
    async def first_page(self, button, interaction):
        await self.show_page(0)

    @ui.button(emoji='<:left:893612797743759431>', style=ButtonStyle.gray)
    async def before_page(self, button, interaction):
        await self.show_checked_page(self.current_page - 1)

    @ui.button(label='Change Mode', style=ButtonStyle.gray)
    async def normal_endless(self, button, interaction):
        self.endless = (not self.endless)
        await self.show_current_page()

    @ui.button(emoji='<:right:893612798242856962>', style=ButtonStyle.gray)
    async def next_page(self, button, interaction):
        await self.show_checked_page(self.current_page + 1)

    @ui.button(emoji='<:rightmost:935926623591612506>', style=ButtonStyle.gray)
    async def last_page(self, button, interaction):
        await self.show_page(self._source.get_max_pages() - 1)


class Invite(ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(
            ui.Button(
                label=f"Invite me!",
                url=r"https://discord.com/api/oauth2/authorize?client_id=824289599065030756&permissions=309238025280&scope=bot%20applications.commands",
                style=ButtonStyle.gray
            )
        )
