from __future__ import annotations

# std
from typing import Annotated, Any, Literal, Optional, overload

# packages
import discord
from discord import Interaction, app_commands
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorCollection

# local
from bot import Advinas
from common.source import TagSource
from common.views import Paginator
from common.custom import (
    Context,
    Tag,
    TagAlias,
    TagName,
    TagError
)


class Tags(commands.Cog):
    def __init__(self, bot: Advinas):
        self.bot = bot
        self.cache: dict[int, dict[str, Tag | TagAlias]] = {}
        bot.loop.create_task(self.ready())

    async def ready(self):
        await self.bot.wait_until_ready()
        self.col: AsyncIOMotorCollection = self.bot.DB.tags
        await self.cache_tags()
        '''
        Document Schema:
        {
            "_id": ObjectId(12345678987654321),
            "guild": 48652105811346421,
            "tags": [
                {
                    "name": "some random tag name", 
                    "content": "lol",
                    "uses": 0,
                    "owner_id": 305106531053107,
                    "created_at": "Wed Apr  6 10:50:12 2022"
                },
                {
                    "name": "some random alias name",
                    "alias": "original tag name",
                    "owner_id": 305106531053107,
                    "created_at": "Wed Apr  6 11:35:17 2022"
                }
            ]
        }
        '''

    async def cog_check(self, ctx: Context) -> bool:
        return ctx.guild is not None

    async def _fetch_tag(self, guild_id: int, name: str) -> Optional[dict[str, Any]]:
        ret: Optional[dict[str, Any]] = await self.col.find_one(
            {'guild': guild_id, 'tags.name': name.lower()},
            {'_id': 0, 'guild': 1, 'tags.$': 1}
        )
        if ret is None:
            if await self.col.find_one({'guild': guild_id}) is None:
                await self.col.insert_one({'guild': guild_id, 'tags': []})
        return ret

    async def _create_tag(self, ctx: Any, name: str, content: str) -> None:
        await self.col.update_one(
            {'guild': ctx.guild.id},
            {'$push': {'tags': {
                'name': name.lower(), 'content': content, 'uses': 0, 'owner_id': ctx.author.id, 'created_at': ctx.message.created_at
            }}}
        )

    async def _create_alias(self, ctx: Any, new_name: str, old_name: str) -> None:
        await self.col.update_one(
            {'guild': ctx.guild.id},
            {'$push': {'tags': {
                'name': new_name.lower(), 'alias': old_name.lower(), 'owner_id': ctx.author.id, 'created_at': ctx.message.created_at
            }}}
        )

    async def used_tag(self, tag: Tag) -> None:
        await self.col.update_one({'guild': tag.guild_id, 'tags.name': tag.name}, {'$inc': {'tags.$.uses': 1}})

    async def delete_tag(self, tag: Tag | TagAlias) -> None:
        await self.col.update_one({'guild': tag.guild_id}, {'$pull': {'tags': {'name': tag.name}}})

    async def edit_tag(self, tag: Tag, content: str) -> None:
        await self.col.update_one(
            {'guild': tag.guild_id, 'tags.name': tag.name},
            {'$set': {'tags.$.content': content}}
        )

    async def get_tag_list(self, guild_id: int, member_id: Optional[int]) -> list[dict[str, Any]]:
        if member_id is not None:
            resp: Optional[Any] = await self.col.aggregate([
                {'$unwind': '$tags'},
                {'$match': {'guild': guild_id, 'tags.owner_id': member_id}},
                {'$project': {
                    'name': '$tags.name',
                    'uses': '$tags.uses',
                    'alias': '$tags.alias',
                    '_id': 0
                }}]).to_list(None)
            if resp is not None:
                return resp
        else:
            resp: Optional[Any] = await self.col.find_one({'guild': guild_id})
            if resp is not None and resp['tags'] != []:
                return resp['tags']
        location = 'for that user' if member_id else 'in that guild'
        raise TagError(f'No tags found {location}.')

    def _get_tag(self, guild_id: int, name: str) -> Optional[Tag | TagAlias]:
        return self.cache.get(guild_id, {}).get(name, None)

    @overload
    async def get_tag(self, guild_id: int, name: str, *, no_alias: bool = False, return_alias: Literal[False] = False) -> Tag:
        ...

    @overload
    async def get_tag(self, guild_id: int, name: str, *, no_alias: bool = False, return_alias: Literal[True] = True) -> Tag | TagAlias:
        ...

    async def get_tag(self, guild_id: int, name: str, *, no_alias: bool = False, return_alias: bool = False) -> Tag | TagAlias:
        tag: Optional[Tag | TagAlias] = self._get_tag(guild_id, name)
        if tag is None:
            raise TagError('Tag not found.')
        if isinstance(tag, TagAlias):
            if (main_tag := self._get_tag(tag.guild_id, tag.alias)) is None:
                await self.delete_tag(Tag.minimal(name, guild_id))
                await self.cache_tags()
                raise TagError('Tag not found.')
            if no_alias:
                raise TagError('You may not edit an alias.')
            if not return_alias:
                return main_tag
        return tag

    async def create_tag(self, ctx: Any, name: str, content: str) -> None:
        if self._get_tag(ctx.guild.id, name):
            raise TagError(f'A tag with the name "{name}" already exists.')
        await self._create_tag(ctx, name, content)
        await ctx.reply(f'Tag "{name}" successfully created.')

    async def create_alias(self, ctx: Any, new_name: str, old_name: str) -> None:
        if self._get_tag(ctx.guild.id, new_name):
            raise TagError(f'A tag with the name "{new_name}" already exists.')
        if (tag := self._get_tag(ctx.guild.id, old_name)) is None:
            raise TagError(
                f'A tag with the name "{old_name}" does not exist.')
        else:
            if isinstance(tag, TagAlias):
                raise TagError('Cannot link an alias to another alias.')
        await self._create_alias(ctx, new_name, old_name)
        await ctx.reply(f'Tag alias "{new_name}" that points to "{old_name}" successfully created.')

    @staticmethod
    def is_privileged(ctx: Context, tag: Tag | TagAlias) -> None:
        author: Any = ctx.author
        if author.id != tag.owner_id:
            if not (author.guild_permissions.manage_guild or author.guild_permissions.administrator):
                raise TagError(
                    'This is not your tag and you do not have the `manage server` permission.')

    async def cache_tags(self) -> None:
        async for doc in self.col.find({}, {'_id': 0, 'guild': 1, 'tags': 1}):
            tags = doc['tags']
            self.cache[doc['guild']] = {
                t['name']: (Tag(**t, guild_id=doc['guild']) if 'alias' not in t else TagAlias(**t, guild_id=doc['guild'])) for t in tags}

    @commands.command(name='cache')
    @commands.is_owner()
    async def _cache(self, ctx: Context) -> None:
        await self.cache_tags()
        await ctx.reply('Cache updated.')

    @app_commands.command(name='t', description='Gets and shows the tag with the given name.')
    @app_commands.guild_only()
    @app_commands.describe(name='The name of the tag you want to see.')
    async def tag_command(self, inter: Interaction, name: str) -> None:
        name = name.lower().strip().replace('\n', '')
        try:
            if not name:
                raise commands.BadArgument('Missing tag name.')
            if len(name) > 100:
                raise commands.BadArgument(
                    'Tag name is a maximum of 100 characters.')

            assert inter.guild is not None
            tag = await self.get_tag(inter.guild.id, name)
        except (commands.BadArgument, TagError) as e:
            await inter.response.send_message(e)
            if isinstance(inter.client, Advinas):
                em = discord.Embed(
                    title=f"**Tag Command** used in `{inter.channel}`", colour=discord.Color.red()
                ).set_footer(
                    text=f"Command run by {inter.user.name}", icon_url=inter.user.display_avatar.url
                ).add_field(
                    name='**Success**', value='`False`', inline=False
                ).add_field(
                    name='**Arguments**', value=f'`/t` name=`{name}`', inline=False
                ).add_field(
                    name='**Reason', value=e, inline=False
                )
                await self.bot._log.send(embed=em)
            return

        await inter.response.send_message(tag.content)
        await self.used_tag(tag)

        if isinstance(inter.client, Advinas):
            em = discord.Embed(
                title=f"**Tag Command** used in `{inter.channel}`", colour=discord.Color.green()
            ).set_footer(
                text=f"Command run by {inter.user.name}", icon_url=inter.user.display_avatar.url
            ).add_field(
                name='**Success**', value='`True`', inline=False
            ).add_field(
                name='**Arguments**', value=f'`/t` name=`{name}`', inline=False
            )
            await self.bot._log.send(embed=em)

    @commands.hybrid_group(name='tag', aliases=['t'], description='Gets and shows the tag with the given name.', fallback='get')
    @app_commands.guild_only()
    @app_commands.describe(name='The name of the tag you want to see.')
    async def tag(self, ctx: Context, *, name: Annotated[str, TagName]):
        assert ctx.guild is not None
        tag = await self.get_tag(ctx.guild.id, name)

        await ctx.reply(tag.content)
        await ctx.log()

        # update the usage
        await self.used_tag(tag)

    @tag.command(name='create', aliases=['make'], description='Creates a new tag with the given name and content.')
    @app_commands.guild_only()
    @app_commands.describe(name='The name of the new tag you want to create.', content='The content of the tag.')
    async def _create(self, ctx: Context, name: Annotated[str, TagName], *, content: Annotated[str, commands.clean_content]):
        if len(content) > 2000:
            return await ctx.send('Tag content is a maximum of 2000 characters.')

        await self.create_tag(ctx, name, content)
        await self.cache_tags()

        await ctx.log()

    @tag.command(name='alias', description='Creates an alias tag that points to another tag.')
    @app_commands.guild_only()
    @app_commands.describe(new_name='The name of the alias.', old_name='The name of the tag you want to refer to.')
    async def _alias(self, ctx: Context, new_name: Annotated[str, TagName], *, old_name: Annotated[str, TagName]):
        await self.create_alias(ctx, new_name, old_name)
        await self.cache_tags()

        await ctx.log()

    @tag.command(name='edit', description='Edits an existing tag. Aliases may not be edited.')
    @app_commands.guild_only()
    @app_commands.describe(name='The name of the new tag you want to edit.', content='The new content of the tag.')
    async def _edit(self, ctx: Context, name: Annotated[str, TagName], *, content: Annotated[str, commands.clean_content]):
        assert ctx.guild is not None
        tag = await self.get_tag(ctx.guild.id, name, no_alias=True)
        self.is_privileged(ctx, tag)

        await self.edit_tag(tag, content)
        await ctx.reply(f'Tag "{name}" successfully edited.')
        await self.cache_tags()

        await ctx.log()

    @tag.command(name='remove', aliases=['delete'], description='Deletes the tag with the given name.')
    @app_commands.guild_only()
    @app_commands.describe(name='The name of the tag you want to remove.')
    async def _remove(self, ctx: Context, name: Annotated[str, TagName]):
        assert ctx.guild is not None
        tag = await self.get_tag(ctx.guild.id, name, return_alias=True)
        self.is_privileged(ctx, tag)

        await self.delete_tag(tag=tag)
        await ctx.reply(f'Tag "{name}" successfully deleted.')
        await self.cache_tags()

        await ctx.log()

    @tag.command(name='info', description='Shows useful information about the tag with the given name.')
    @app_commands.guild_only()
    @app_commands.describe(name='The name of the tag you want to see information about.')
    async def _info(self, ctx: Context, *, name: Annotated[str, TagName]):
        assert ctx.guild is not None
        tag = await self.get_tag(ctx.guild.id, name)

        em = discord.Embed(title=tag.name, timestamp=tag.created_at)
        user = self.bot.get_user(tag.owner_id) or (await self.bot.fetch_user(tag.owner_id))
        em.set_author(name=str(user), icon_url=user.display_avatar.url)
        em.add_field(name='Owner', value=f'<@{tag.owner_id}>')
        em.add_field(name='Uses', value=tag.uses)
        em.set_footer(text='Tag created at (UTC)')

        await ctx.reply(embed=em)
        await ctx.log()

    @tag.command(name='list', description='Shows a list of tags available in this server.')
    @app_commands.guild_only()
    async def _list(self, ctx: Context, *, member: Optional[discord.Member] = None):
        assert ctx.guild is not None
        member_id = member.id if member is not None else None
        name = member.name if member is not None else ctx.guild.name
        tag_list = await self.get_tag_list(ctx.guild.id, member_id)

        await ctx.log()
        await Paginator(TagSource(tag_list, name, ctx.author)).start(ctx)

    # @tag.command(name='search')
    # async def _search(self, ctx, *, query: commands.clean_content):
    #     ...


async def setup(bot: Advinas):
    await bot.add_cog(Tags(bot))
