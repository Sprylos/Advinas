from __future__ import annotations

# std
from typing import Any, Callable, Coroutine, Generic, Sequence, TypeVar, TYPE_CHECKING
from typing_extensions import Self

# packages
import discord
import wavelink
from infinitode import Leaderboard

# locals
from common.custom import Tag, TagAlias
from common.utils import codeblock

if TYPE_CHECKING:
    from common.pagination import Paginator


S = TypeVar("S", bound="Sequence[Any]")


class ListSource(Generic[S]):
    def __init__(
        self,
        entries: S,
        title: str,
        user: discord.User | discord.Member,
        *,
        per_page: int = 20,
    ) -> None:
        assert entries and per_page > 1

        self._title = title
        self._user = user
        self._per_page = per_page

        self._init_entries(entries)

    def _init_entries(self, entries: S) -> None:
        pages, left_over = divmod(len(entries), self._per_page)
        if left_over:
            pages += 1

        self._entries: S = entries
        self.max_pages: int = pages
        self.needs_pagination: bool = len(entries) > pages

    async def prepare_once(self) -> None:
        pass

    def get_page(self, page_number: int) -> S:
        base = page_number * self._per_page
        return self._entries[base : base + self._per_page]  # type: ignore

    def page_description(self, paginator: Paginator[Self], page: S) -> str:
        raise NotImplementedError

    def format_page(self, paginator: Paginator[Self], page: S) -> discord.Embed:
        em = discord.Embed(
            title=self._title,
            description=self.page_description(paginator, page),
            colour=60415,
        )
        return em.set_footer(
            text=f"Requested by {self._user}", icon_url=self._user.display_avatar.url
        )


class LeaderboardSource(ListSource[Leaderboard]):
    def __init__(
        self,
        title: str | Callable[[Leaderboard], str],
        user: discord.User | discord.Member,
        mapper: Callable[[bool, bool], Coroutine[Any, Any, Leaderboard]],
    ) -> None:
        if isinstance(title, str):
            self._title: str = title
        else:
            self.__title_mapper = title

        self._user = user
        self._per_page = 20

        self.__cache: dict[int, Leaderboard] = {}
        self.__mapper = mapper
        self.__prefix: str

    async def prepare_once(self) -> None:
        await self.get_and_set_entries(False, False)

        try:
            self._title = self.__title_mapper(self._entries)
        except AttributeError:
            pass
        else:
            del self.__title_mapper

    async def get_and_set_entries(
        self, beta: bool, endless: bool, inter: discord.Interaction | None = None
    ) -> None:
        code = beta | endless << 1
        entries = self.__cache.get(code, None)
        if entries is None:
            if inter is not None and not inter.response.is_done():
                await inter.response.defer()

            entries = await self.__mapper(beta, endless)
            self.__cache[code] = entries

        version = "[Beta] " if beta else ""
        mode = "Endless" if endless else "Normal"
        self.__prefix = f"{version}Player Count {mode}"

        self.beta = beta
        self.endless = endless
        self._init_entries(entries)

    def page_description(self, paginator: Paginator[Self], page: Leaderboard) -> str:
        return codeblock(f"{self.__prefix}: {page.total}\n" + page.format_scores())


class TagSource(ListSource[list[Tag | TagAlias]]):
    async def prepare_once(self) -> None:
        self.alphabetical_sorted = True
        self._entries.sort(key=lambda t: t.name)

    def swap_sorting(self) -> None:
        self.alphabetical_sorted = not self.alphabetical_sorted
        if self.alphabetical_sorted:
            self._entries.sort(key=lambda t: t.name)
        else:
            self._entries.sort(key=lambda t: getattr(t, "uses", -1), reverse=True)

    def page_description(
        self, paginator: Paginator[Self], page: Sequence[Tag | TagAlias]
    ) -> str:
        description = "\n".join(
            [
                (
                    f"{tag.name} (Uses: {tag.uses})"
                    if not isinstance(tag, TagAlias)
                    else f'{tag.name} (Alias to "{tag.alias}")'
                )
                for tag in page
            ]
        )
        return codeblock(description)


class QueueSource(ListSource[list[wavelink.Playable]]):
    def __init__(
        self,
        entries: list[wavelink.Playable],
        title: str,
        user: discord.User | discord.Member,
    ) -> None:
        super().__init__(entries, title, user, per_page=15)

    def page_description(
        self, paginator: Paginator[Self], page: list[wavelink.Playable]
    ) -> str:
        return "\n".join(
            [
                f"{paginator.current_page * 15 + c}. [{track.title}]({track.uri}) by {track.author}"
                for c, track in enumerate(page, start=1)
            ]
        )
