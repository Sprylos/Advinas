from __future__ import annotations

# std
from typing import Any

# packages
import discord
from discord.ext import menus

# local
from common.custom import Context
from common.source import TagSource
from .source import LBSource, ScoreLBSource

gray_style = discord.ButtonStyle.gray


class Paginator(discord.ui.View, menus.MenuPages):
    def __init__(self, source: LBSource | Any):
        super().__init__(timeout=60)
        self._source = source
        self.delete_message_after = False
        self.current_page = 0

    async def start(self, ctx: Context, *, channel: discord.TextChannel | None = None, wait: bool = False) -> None:
        await self._source._prepare_once()
        self.ctx = ctx
        page = await self._source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        self.message: discord.Message = await ctx.reply(**kwargs)

    async def show_page(self, inter: discord.Interaction, page_number: int) -> None:
        page: Any = await self._source.get_page(page_number)
        self.current_page = page_number
        kwargs = await self._get_kwargs_from_page(page)
        await inter.response.edit_message(**kwargs)

    async def show_checked_page(self, inter: discord.Interaction, page_number: int):
        max_pages = self._source.get_max_pages()
        try:
            if max_pages is None:
                # If it doesn't give maximum pages, it cannot be checked
                await self.show_page(inter, page_number)
            elif max_pages > page_number >= 0:
                await self.show_page(inter, page_number)
        except IndexError:
            # An error happened that can be handled, so ignore it.
            pass

    async def show_current_page(self):
        if self._source.is_paginating():
            page_number = self.current_page
            page: Any = await self._source.get_page(page_number)
            kwargs = await self._get_kwargs_from_page(page)
            await self.message.edit(**kwargs)

    async def _get_kwargs_from_page(self, page: Any) -> dict[str, Any]:
        value: dict[str, Any]
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

    def manage_buttons(self, new_page: int):
        if new_page == 0:
            self.first_page.disabled = True
            self.before_page.disabled = True
            if self._source.get_max_pages() > 1:
                self.next_page.disabled = False
                self.last_page.disabled = False
            else:
                self.next_page.disabled = True
                self.last_page.disabled = True
        elif new_page == self._source.get_max_pages() - 1:
            self.first_page.disabled = False
            self.before_page.disabled = False
            self.next_page.disabled = True
            self.last_page.disabled = True
        else:
            self.first_page.disabled = False
            self.before_page.disabled = False
            self.next_page.disabled = False
            self.last_page.disabled = False

    @discord.ui.button(emoji='<:leftmost:935926623230910535>', disabled=True, style=gray_style)
    async def first_page(self, inter: discord.Interaction, button: Any):
        self.manage_buttons(0)
        await self.show_page(inter, 0)

    @discord.ui.button(emoji='<:left:893612797743759431>', disabled=True, style=gray_style)
    async def before_page(self, inter: discord.Interaction, button: Any):
        self.manage_buttons(self.current_page - 1)
        await self.show_checked_page(inter, self.current_page - 1)

    @discord.ui.button(emoji='<:right:893612798242856962>', style=gray_style)
    async def next_page(self, inter: discord.Interaction, button: Any):
        new_page = self.current_page + 1
        if new_page == self._source.get_max_pages():
            self.next_page.disabled = True
            self.last_page.disabled = True
            return await self.show_current_page()
        self.manage_buttons(new_page)
        await self.show_checked_page(inter, new_page)

    @discord.ui.button(emoji='<:rightmost:935926623591612506>', style=gray_style)
    async def last_page(self, inter: discord.Interaction, button: Any):
        self.manage_buttons(self._source.get_max_pages() - 1)
        await self.show_page(inter, self._source.get_max_pages() - 1)


class TagPaginator(Paginator):
    def __init__(self, source: TagSource):
        super().__init__(source)
        self._source: TagSource

    async def show_current_page(self, inter: discord.Interaction | None = None):
        if self._source.is_paginating():
            page_number = self.current_page
            page: Any = await self._source.get_page(page_number)
            kwargs = await self._get_kwargs_from_page(page)
            if inter is not None:
                await inter.response.edit_message(**kwargs)
            else:
                await self.message.edit(**kwargs)

    @discord.ui.button(emoji='<:numericalsorting:1081676364366745671>', style=gray_style)
    async def swap_sorting(self, inter: discord.Interaction, button: Any):
        self._source.swap_sorting()
        self.swap_sorting.emoji = '<:numericalsorting:1081676364366745671>' if self._source.alphabetical_sorted else '<:alphabeticalsorting:1081676474924408912>'
        await self.show_current_page(inter)


class ScorePaginator(discord.ui.View, menus.MenuPages):
    def __init__(self, source: ScoreLBSource):
        super().__init__(timeout=60)
        self._source = source
        self.current_page = 0
        self.delete_message_after = False
        self.endless: bool = False

    async def start(self, ctx: Context, *, channel: discord.TextChannel | None = None, wait: bool = False) -> None:
        await self._source._prepare_once()
        self.ctx = ctx
        page = await self._source.get_page(self, 0)
        kwargs = await self._get_kwargs_from_page(page)
        self.message: discord.Message = await ctx.reply(**kwargs)

    async def show_page(self, inter: discord.Interaction, page_number: int) -> None:
        page: Any = await self._source.get_page(self, page_number)
        self.current_page = page_number
        kwargs = await self._get_kwargs_from_page(page)
        await inter.response.edit_message(**kwargs)

    async def show_checked_page(self, inter: discord.Interaction, page_number: int):
        max_pages = self._source.get_max_pages()
        try:
            if max_pages is None:
                # If it doesn't give maximum pages, it cannot be checked
                await self.show_page(inter, page_number)
            elif max_pages > page_number >= 0:
                await self.show_page(inter, page_number)
        except IndexError:
            # An error happened that can be handled, so ignore it.
            pass

    async def show_current_page(self, inter: discord.Interaction | None = None):
        if self._source.is_paginating():
            page_number = self.current_page
            page: Any = await self._source.get_page(self, page_number)
            kwargs = await self._get_kwargs_from_page(page)
            if inter is not None:
                await inter.response.edit_message(**kwargs)
            else:
                await self.message.edit(**kwargs)

    async def _get_kwargs_from_page(self, page: Any) -> dict[str, Any]:
        value: dict[str, Any]
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

    def manage_buttons(self, new_page: int):
        if new_page == 0:
            self.first_page.disabled = True
            self.before_page.disabled = True
            if self._source.get_max_pages() > 1:
                self.next_page.disabled = False
                self.last_page.disabled = False
            else:
                self.next_page.disabled = True
                self.last_page.disabled = True
        elif new_page == self._source.get_max_pages() - 1:
            self.first_page.disabled = False
            self.before_page.disabled = False
            self.next_page.disabled = True
            self.last_page.disabled = True
        else:
            self.first_page.disabled = False
            self.before_page.disabled = False
            self.next_page.disabled = False
            self.last_page.disabled = False

    @discord.ui.button(emoji='<:leftmost:935926623230910535>', disabled=True, style=gray_style)
    async def first_page(self, inter: discord.Interaction, button: Any):
        self.manage_buttons(0)
        await self.show_page(inter, 0)

    @discord.ui.button(emoji='<:left:893612797743759431>', disabled=True, style=gray_style)
    async def before_page(self, inter: discord.Interaction, button: Any):
        self.manage_buttons(self.current_page - 1)
        await self.show_checked_page(inter, self.current_page - 1)

    @discord.ui.button(label='Change Mode', style=gray_style)
    async def normal_endless(self, inter: discord.Interaction, button: Any):
        self.endless = (not self.endless)
        await self.show_current_page(inter)

    @discord.ui.button(emoji='<:right:893612798242856962>', style=gray_style)
    async def next_page(self, inter: discord.Interaction, button: Any):
        new_page = self.current_page + 1
        if new_page == self._source.get_max_pages():
            self.next_page.disabled = True
            self.last_page.disabled = True
            return await self.show_current_page()
        self.manage_buttons(new_page)
        await self.show_checked_page(inter, new_page)

    @discord.ui.button(emoji='<:rightmost:935926623591612506>', style=gray_style)
    async def last_page(self, inter: discord.Interaction, button: Any):
        self.manage_buttons(self._source.get_max_pages() - 1)
        await self.show_page(inter, self._source.get_max_pages() - 1)


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
