# std
from typing import (
    Annotated,
    Any,
    Dict,
    List,
    Optional,
)
# packages
import discord
from discord import app_commands
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorCollection

# local
from bot import Advinas
from common.source import TagSource
from common.views import Paginator
from common.custom import (
    Context,
    Tag,
    TagName,
    TagError
)


class Tags(commands.Cog):
    def __init__(self, bot: Advinas):
        self.bot = bot
        bot.loop.create_task(self.ready())

    async def ready(self):
        await self.bot.wait_until_ready()
        self.col: AsyncIOMotorCollection = self.bot.DB.tags
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

    async def _get_tag(self, guild_id: int, name: str) -> Optional[Dict[str, Any]]:
        ret: Optional[Dict[str, Any]] = await self.col.find_one(
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

    async def delete_tag(self, tag: Tag) -> None:
        await self.col.update_one({'guild': tag.guild_id}, {'$pull': {'tags': {'name': tag.name}}})

    async def edit_tag(self, tag: Tag, content: str) -> None:
        await self.col.update_one(
            {'guild': tag.guild_id, 'tags.name': tag.name},
            {'$set': {'tags.$.content': content}}
        )

    async def get_tag_list(self, guild_id: int, member_id: Optional[int]) -> List[Dict[str, Any]]:
        query = {'guild': guild_id}
        projection = 'tags'
        if member_id is not None:
            query.update({'tags.owner_id': member_id})
            projection += '.$'
        ret: Optional[Dict[str, List[Dict[str, Any]]]] = await self.col.find_one(query, {projection: 1})
        if ret is None or ret['tags'] == []:
            if member_id is not None:
                if await self.col.find_one({'guild': guild_id}) is None:
                    await self.col.insert_one({'guild': guild_id, 'tags': []})
            location = 'for that user' if member_id else 'in that guild'
            raise TagError(f'No tags found {location}.')
        return ret['tags']

    async def get_tag(self, guild_id: int, name: str, *, no_alias: bool = False) -> Tag:
        if (res := await self._get_tag(guild_id, name)) is None:
            raise TagError('Tag not found.')
        if (alias := res['tags'][0].get('alias', None)) is not None:
            if (result := await self._get_tag(guild_id, alias)) is None:
                await self.delete_tag(Tag.minimal(res['tags'][0]['name'], res['guild']))
                raise TagError('Tag not found.')
            if no_alias:
                raise TagError('You may not edit an alias.')
            res = result
        return Tag.from_db(res)

    async def create_tag(self, ctx: Any, name: str, content: str) -> None:
        if await self._get_tag(ctx.guild.id, name):
            raise TagError(f'A tag with the name "{name}" already exists.')
        await self._create_tag(ctx, name, content)
        await ctx.reply(f'Tag "{name}" successfully created.')

    async def create_alias(self, ctx: Any, new_name: str, old_name: str) -> None:
        if await self._get_tag(ctx.guild.id, new_name):
            raise TagError(f'A tag with the name "{new_name}" already exists.')
        if (tag := await self._get_tag(ctx.guild.id, old_name)) is None:
            raise TagError(
                f'A tag with the name "{old_name}" does not exist.')
        else:
            if hasattr(tag, 'alias'):
                raise TagError('Cannot link an alias to another alias.')
        await self._create_alias(ctx, new_name, old_name)
        await ctx.reply(f'Tag alias "{new_name}" that points to "{old_name}" successfully created.')

    @staticmethod
    async def is_privileged(ctx: Context, tag: Tag) -> None:
        author: Any = ctx.author
        if author.id != tag.owner_id:
            if not (author.guild_permissions.manage_guild or author.guild_permissions.administrator):
                raise TagError(
                    'This is not your tag and you do not have the manager server permission.')

    @commands.hybrid_group(name='tag', description='Gets and shows the tag with the given name.', fallback='get')
    @app_commands.guild_only()
    @app_commands.describe(name='The name of the tag you want to see.')
    async def tag(self, ctx: Context, *, name: Annotated[str, TagName]):
        # guild is never None
        tag = await self.get_tag(ctx.guild.id, name)  # type: ignore

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

        await ctx.log()

    @tag.command(name='alias', description='Creates an alias tag that points to another tag.')
    @app_commands.guild_only()
    @app_commands.describe(new_name='The name of the alias.', old_name='The name of the tag you want to refer to.')
    async def _alias(self, ctx: Context, new_name: Annotated[str, TagName], *, old_name: Annotated[str, TagName]):
        await self.create_alias(ctx, new_name, old_name)

        await ctx.log()

    @tag.command(name='edit', description='Edits an existing tag. Aliases may not be edited.')
    @app_commands.guild_only()
    @app_commands.describe(name='The name of the new tag you want to edit.', content='The new content of the tag.')
    async def _edit(self, ctx: Context, name: Annotated[str, TagName], *, content: Annotated[str, commands.clean_content]):
        # guild is never None
        tag = await self.get_tag(ctx.guild.id, name, no_alias=True)  # type: ignore # nopep8
        await self.is_privileged(ctx, tag)

        await self.edit_tag(tag, content)
        await ctx.reply(f'Tag "{name}" successfully edited.')
        await ctx.log()

    @tag.command(name='remove', aliases=['delete'], description='Deletes the tag with the given name.')
    @app_commands.guild_only()
    @app_commands.describe(name='The name of the tag you want to remove.')
    async def _remove(self, ctx: Context, name: Annotated[str, TagName]):
        # guild is never None
        tag = await self.get_tag(ctx.guild.id, name)  # type: ignore
        await self.is_privileged(ctx, tag)

        await self.delete_tag(tag=tag)
        await ctx.reply(f'Tag "{name}" successfully deleted.')
        await ctx.log()

    @tag.command(name='info', description='Shows useful information about the tag with the given name.')
    @app_commands.guild_only()
    @app_commands.describe(name='The name of the tag you want to see information about.')
    async def _info(self, ctx: Context, *, name: Annotated[str, TagName]):
        # guild is never None
        tag = await self.get_tag(ctx.guild.id, name)  # type: ignore

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
    async def _list(self, ctx: Context, member: Optional[discord.Member] = None):
        member_id = member.id if member is not None else None
        name = member.name if member is not None else ctx.guild.name  # type: ignore
        tag_list = await self.get_tag_list(ctx.guild.id, member_id)  # type: ignore # nopep8

        await ctx.log()
        await Paginator(TagSource(tag_list, name, ctx.author)).start(ctx)

    # @tag.command(name='search')
    # async def _search(self, ctx, *, query: commands.clean_content):
    #     ...


async def setup(bot: Advinas):
    await bot.add_cog(Tags(bot))
