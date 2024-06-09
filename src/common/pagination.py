from __future__ import annotations

# std
from typing import Any, Generic, TypeVar
from typing_extensions import Self

# packages
import discord

# local
from common.custom import Context
from common.source import ListSource, TagSource, LeaderboardSource


LS = TypeVar("LS", bound="ListSource[Any]")


class Paginator(discord.ui.View, Generic[LS]):
    def __init__(self, ctx: Context, source: LS) -> None:
        super().__init__(timeout=60)
        self.ctx = ctx
        self.source = source
        self.current_page = 0

    @classmethod
    async def start_with_source(
        cls, ctx: Context, source: LS, **kwargs: Any
    ) -> Paginator[LS]:
        paginator = cls(ctx, source, **kwargs)
        await paginator.start(ctx)
        return paginator

    async def start(self, ctx: Context) -> None:
        await self.source.prepare_once()
        page = self.source.get_page(0)
        embed = self.source.format_page(self, page)
        self.message: discord.Message = await ctx.reply(embed=embed, view=self)

    async def show_page(self, inter: discord.Interaction, page_number: int) -> None:
        if page_number < 0 or page_number >= self.source.max_pages:
            return

        self.current_page = page_number
        page = self.source.get_page(page_number)
        embed = self.source.format_page(self, page)

        if inter.response.is_done():
            await inter.followup.edit_message(self.message.id, embed=embed, view=self)
        else:
            await inter.response.edit_message(embed=embed, view=self)

    async def show_current_page(self, inter: discord.Interaction | None = None) -> None:
        if not self.source.needs_pagination:
            return

        page_number = self.current_page
        page = self.source.get_page(page_number)
        embed = self.source.format_page(self, page)

        if inter is None:
            await self.message.edit(embed=embed, view=self)
        elif inter.response.is_done():
            await inter.followup.edit_message(self.message.id, embed=embed, view=self)
        else:
            await inter.response.edit_message(embed=embed, view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the author that invoked the command to be able to use the interaction."""
        if interaction.user == self.ctx.author:
            return True

        await interaction.response.send_message(
            "This is not your interaction!", ephemeral=True
        )
        return False

    async def on_timeout(self) -> None:
        for button in self.children:
            button.disabled = True  # type: ignore
        await self.show_current_page()

    def manage_buttons(self, new_page: int) -> None:
        self.first_page.disabled = self.before_page.disabled = new_page <= 0
        self.next_page.disabled = self.last_page.disabled = (
            new_page >= self.source.max_pages - 1
        )

    @discord.ui.button(emoji="<:leftmost:935926623230910535>", disabled=True, row=0)
    async def first_page(
        self, inter: discord.Interaction, button: discord.ui.Button[Self]
    ) -> None:
        self.manage_buttons(0)
        await self.show_page(inter, 0)

    @discord.ui.button(emoji="<:left:893612797743759431>", disabled=True, row=0)
    async def before_page(
        self, inter: discord.Interaction, button: discord.ui.Button[Self]
    ) -> None:
        self.manage_buttons(self.current_page - 1)
        await self.show_page(inter, self.current_page - 1)

    @discord.ui.button(emoji="<:right:893612798242856962>", row=0)
    async def next_page(
        self, inter: discord.Interaction, button: discord.ui.Button[Self]
    ) -> None:
        self.manage_buttons(self.current_page + 1)
        await self.show_page(inter, self.current_page + 1)

    @discord.ui.button(emoji="<:rightmost:935926623591612506>", row=0)
    async def last_page(
        self, inter: discord.Interaction, button: discord.ui.Button[Self]
    ) -> None:
        self.manage_buttons(self.source.max_pages - 1)
        await self.show_page(inter, self.source.max_pages - 1)


class LeaderboardPaginator(Paginator[LeaderboardSource]):
    def __init__(
        self, ctx: Context, source: LeaderboardSource, has_endless: bool = True
    ) -> None:
        super().__init__(ctx, source)

        if has_endless is False:
            self.remove_item(self.normal_endless)
            self.remove_item(self.live_beta)
            self.live_beta.row = 0
            self.add_item(self.live_beta)  # refresh the row

    async def start(self, ctx: Context) -> None:
        async with ctx.typing():
            return await super().start(ctx)

    @discord.ui.button(label="Beta", style=discord.ButtonStyle.primary, row=1)
    async def live_beta(
        self, inter: discord.Interaction, button: discord.ui.Button[Self]
    ) -> None:
        button.label = "Beta" if self.source.beta else "Live"
        await self.source.get_and_set_entries(
            not self.source.beta, self.source.endless, inter
        )
        await self.first_page.callback(inter)

    @discord.ui.button(label="Endless", style=discord.ButtonStyle.primary, row=1)
    async def normal_endless(
        self, inter: discord.Interaction, button: discord.ui.Button[Self]
    ) -> None:
        self.normal_endless.label = "Endless" if self.source.endless else "Normal"
        await self.source.get_and_set_entries(
            self.source.beta, not self.source.endless, inter
        )
        await self.first_page.callback(inter)


class TagPaginator(Paginator[TagSource]):
    @discord.ui.button(
        emoji="<:numericalsorting:1081676364366745671>",
        style=discord.ButtonStyle.primary,
    )
    async def swap_sorting(
        self, inter: discord.Interaction, button: discord.ui.Button[Self]
    ) -> None:
        self.source.swap_sorting()
        self.swap_sorting.emoji = (
            "<:numericalsorting:1081676364366745671>"
            if self.source.alphabetical_sorted
            else "<:alphabeticalsorting:1081676474924408912>"
        )
        await self.show_current_page(inter)
