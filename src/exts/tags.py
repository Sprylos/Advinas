import discord

from discord.ext import commands
from discord.ext.commands import Context
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from typing_extensions import Self
from motor.motor_asyncio import AsyncIOMotorCollection

from bot import Advinas


class TagName(commands.clean_content):
    def __init__(self, *, lower: bool = False):
        self.lower = lower
        super().__init__()

    async def convert(self, ctx: Context, argument: str) -> str:
        converted = await super().convert(ctx, argument)
        lower = converted.lower().strip()

        if not lower:
            raise commands.BadArgument('Missing tag name.')

        if len(lower) > 100:
            raise commands.BadArgument(
                'Tag name is a maximum of 100 characters.')

        first_word, _, _ = lower.partition(' ')

        # get tag command.
        root = ctx.bot.get_command('tag')
        if first_word in root.all_commands:
            raise commands.BadArgument(
                'This tag name starts with a reserved word.')

        return converted if not self.lower else lower


@dataclass
class Tag:
    name: str
    content: str
    guild_id: int
    uses: int
    owner_id: int
    created_at: datetime

    @classmethod
    def from_db(cls, result: dict[int: dict[str: dict[str: str | int]]], guild_id: Optional[int] = None, name: Optional[str] = None) -> Self:
        if not guild_id:
            guild_id = next(iter(result))
        if not name:
            name = next(iter(result[guild_id]))
        at = result[guild_id][name]
        return cls(name, at['content'], guild_id, at['uses'], at['owner_id'], datetime.strptime(at['created_at'], '%c'))


class Tags(commands.Cog):
    def __init__(self, bot: Advinas):
        self.bot = bot
        self.col: AsyncIOMotorCollection = self.bot.DB.tags

    # declare group commands
    # tag_group = app_commands.Group(
    #     name="tag",
    #     description="Shows tags and allows for useful utility."
    # )

    async def cog_check(self, ctx: Context) -> bool:
        return ctx.guild is not None

    async def get_tag(self, guild_id: int, name: str) -> Tag:
        if res := await self.col.find_one({guild_id: {name: {'$exists': True}}}, {'_id': 0}) is None:
            raise RuntimeError('Tag not found.')
        if alias := res[guild_id][name].get('alias', None) is not None:
            if res := await self.col.find_one({guild_id: {alias: {'$exists': True}}}, {'_id': 0}) is None:
                await self.delete_tag(guild_id, name)
                raise RuntimeError('Tag not found.')
        return Tag.from_db(res, guild_id, alias or name)

    # async def search_tags(self, guild_id: int, name: str):
    #     ...

    async def create_tag(self, ctx: Context, name: str, content: commands.clean_content) -> None:
        if await self.get_tag(ctx.guild.id, name):
            raise RuntimeError('A tag with this name already exists.')
        await self.col.insert_one({ctx.guild.id: {name: {'content': content, 'uses': 0, 'owner_id': ctx.author.id, 'created_at': ctx.message.created_at.strftime('%c')}}})
        await ctx.send('Tag successfully created.')

    async def create_alias(self, ctx: Context, new_name: str, old_name: str) -> None:
        if await self.get_tag(ctx.guild.id, new_name):
            raise RuntimeError('A tag with this name already exists.')
        if tag := self.get_tag(ctx.guild.id, old_name) is None:
            raise RuntimeError(f'A tag with the name of "{old_name}" does not exist.')  # nopep8
        else:
            if hasattr(tag, 'alias'):
                raise RuntimeError('Cannot link an alias to another alias.')
        await self.col.insert_one({ctx.guild.id: {new_name: {'alias': old_name, 'owner_id': ctx.author.id, 'created_at': ctx.message.created_at.strftime('%c')}}})
        await ctx.send(f'Tag alias "{new_name}" that points to "{old_name}" successfully created.')

    async def delete_tag(self, guild_id: int, name: str, *, tag: Optional[Tag] = None) -> None:
        if tag:
            guild_id, name = tag.guild_id, tag.name
        await self.col.delete_one({guild_id: {name: {'$exists': True}}})

    async def used_tag(self, tag: Tag) -> None:
        await self.col.update_one({tag.guild_id: {tag.name: {'$exists': True}}}, {tag.guild_id: {tag.name: {'$inc': {'uses': 1}}}})

    @staticmethod
    async def can_delete(ctx: Context, tag: Tag) -> None:
        if ctx.author.id != tag.owner_id:
            if not (ctx.author.guild_permissions.manage_guild or ctx.author.guild_permissions.administrator):
                raise RuntimeError('This is not your tag and you do not have the manager server permission.')  # nopep8

    @commands.group(name='tag', invoke_without_command=True)
    async def tag(self, ctx: Context, *, name: TagName(lower=True)):
        try:
            tag = await self.get_tag(ctx.guild.id, name)
        except RuntimeError as e:
            return await ctx.send(e)
        await ctx.send(tag.content, reference=ctx.replied_reference)

        # update the usage
        await self.used_tag(tag)

    @tag.command(name='create', aliases=['make'])
    async def _create(self, ctx: Context, name: TagName, *, content: commands.clean_content):
        if len(content) > 2000:
            return await ctx.send('Tag content is a maximum of 2000 characters.')

        await self.create_tag(ctx, name, content)

    @tag.command(name='alias')
    async def _alias(self, ctx: Context, new_name: TagName, *, old_name: TagName):
        await self.create_alias(ctx, new_name, old_name)

    @tag.command(name='remove', aliases=['delete'])
    async def _remove(self, ctx: Context, name: TagName(lower=True)):
        try:
            tag = await self.get_tag(ctx.guild.id, name)
            await self.can_delete(ctx, tag)
        except RuntimeError as e:
            return await ctx.send(e)

        await self.delete_tag(tag=tag)
        await ctx.send(f'Tag "{name}" successfully deleted.')

    @tag.command(name='info')
    async def _info(self, ctx: Context, *, name: TagName):
        try:
            tag = await self.get_tag(ctx.guild.id, name)
        except RuntimeError as e:
            return await ctx.send(e)

        em = discord.Embed(title=tag.name, timestamp=tag.created_at)
        user = self.bot.get_user(tag.owner_id) or (await self.bot.fetch_user(tag.owner_id))
        em.set_author(name=str(user), icon_url=user.display_avatar.url)
        em.add_field(name='Owner', value=f'<@{tag.owner_id}>')
        em.add_field(name='Uses', value=tag.uses)
        em.set_footer(text='Tag created at')

        await ctx.send(embed=em)

    # @tag.command(name='search')
    # async def _search(self, ctx, *, query: commands.clean_content):
    #     ...


async def setup(bot: Advinas):
    await bot.add_cog(Tag(bot))
