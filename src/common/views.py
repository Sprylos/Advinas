# std
from typing import (
    Any,
    Dict,
    TYPE_CHECKING
)

# packages
import discord
from discord.ext import menus
from infinitode import Leaderboard

# local
from common.custom import Context
from .source import LBSource, ScoreLBSource

gray_style = discord.ButtonStyle.gray


class Paginator(discord.ui.View, menus.MenuPages):
    def __init__(self, source: LBSource, *, delete_message_after=False):
        super().__init__(timeout=60)
        self._source = source
        self.current_page = 0
        self.delete_message_after = delete_message_after

    async def start(self, ctx: Context, *, channel=None, wait=False) -> None:
        await self._source._prepare_once()
        self.ctx = ctx
        page = await self._source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        self.message: discord.Message = await ctx.send(**kwargs)

    async def show_page(self, page_number: int) -> None:
        page: Leaderboard = await self._source.get_page(page_number)
        self.current_page = page_number
        kwargs = await self._get_kwargs_from_page(page)
        await self.message.edit(**kwargs)

    async def _get_kwargs_from_page(self, page: Leaderboard) -> Dict[str, Any]:
        value: Dict[str, Any]
        value = await super()._get_kwargs_from_page(page)  # type: ignore
        if 'view' not in value:
            value.update({'view': self})
        return value

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the author that invoked the command to be able to use the interaction."""
        if interaction.user == self.ctx.author:
            return True
        else:
            await interaction.response.send_message('This is not your interaction!', ephemeral=True)
            return False

    async def on_timeout(self) -> None:
        for button in self.children:
            button.disabled = True  # type: ignore
        await self.show_current_page()

    @discord.ui.button(emoji='<:leftmost:935926623230910535>', style=gray_style)
    async def first_page(self, inter, button):
        await self.show_page(0)

    @discord.ui.button(emoji='<:left:893612797743759431>', style=gray_style)
    async def before_page(self, inter, button):
        await self.show_checked_page(self.current_page - 1)

    @discord.ui.button(emoji='<:right:893612798242856962>', style=gray_style)
    async def next_page(self, inter, button):
        await self.show_checked_page(self.current_page + 1)

    @discord.ui.button(emoji='<:rightmost:935926623591612506>', style=gray_style)
    async def last_page(self, inter, button):
        await self.show_page(self._source.get_max_pages() - 1)


class ScorePaginator(discord.ui.View, menus.MenuPages):
    def __init__(self, source: ScoreLBSource, *, delete_message_after=False):
        super().__init__(timeout=60)
        self._source = source
        self.current_page = 0
        self.delete_message_after = delete_message_after
        self.endless: bool = False

    async def start(self, ctx: Context, *, channel=None, wait=False) -> None:
        await self._source._prepare_once()
        self.ctx = ctx
        page = await self._source.get_page(self, 0)
        kwargs = await self._get_kwargs_from_page(page)
        self.message: discord.Message = await ctx.send(**kwargs)

    async def show_page(self, page_number: int) -> None:
        page = await self._source.get_page(self, page_number)
        self.current_page = page_number
        kwargs = await self._get_kwargs_from_page(page)
        await self.message.edit(**kwargs)

    async def _get_kwargs_from_page(self, page) -> Dict[str, Any]:
        value: Dict[str, Any]
        value = await super()._get_kwargs_from_page(page)  # type: ignore
        if 'view' not in value:
            value.update({'view': self})
        return value

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the author that invoked the command to be able to use the interaction."""
        if interaction.user == self.ctx.author:
            return True
        else:
            await interaction.response.send_message('This is not your interaction!', ephemeral=True)
            return False

    async def on_timeout(self) -> None:
        for button in self.children:
            button.disabled = True  # type: ignore
        await self.show_current_page()

    @discord.ui.button(emoji='<:leftmost:935926623230910535>', style=gray_style)
    async def first_page(self, inter, button):
        await self.show_page(0)

    @discord.ui.button(emoji='<:left:893612797743759431>', style=gray_style)
    async def before_page(self, inter, button):
        await self.show_checked_page(self.current_page - 1)

    @discord.ui.button(label='Change Mode', style=gray_style)
    async def normal_endless(self, inter, button):
        self.endless = (not self.endless)
        await self.show_current_page()

    @discord.ui.button(emoji='<:right:893612798242856962>', style=gray_style)
    async def next_page(self, inter, button):
        await self.show_checked_page(self.current_page + 1)

    @discord.ui.button(emoji='<:rightmost:935926623591612506>', style=gray_style)
    async def last_page(self, inter, button):
        await self.show_page(self._source.get_max_pages() - 1)


class Invite(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(
            discord.ui.Button(
                label=f"Invite me!",
                url=r"https://discord.com/api/oauth2/authorize?client_id=824289599065030756&permissions=309238025280&scope=bot%20applications.commands",
                style=gray_style
            )
        )
