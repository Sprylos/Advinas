from __future__ import annotations

# std
from typing import Annotated, Any, Literal, overload

# packages
import discord
from discord import Interaction, app_commands
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorCollection

# local
from bot import Advinas
from common.source import TagSource
from common.views import Paginator
from common.errors import TagError
from common.utils import create_choices
from common.custom import (
    Context,
    GuildContext,
    Tag,
    TagAlias,
    TagName,
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

    async def _fetch_tag(self, guild_id: int, name: str) -> dict[str, Any] | None:
        ret: dict[str, Any] | None = await self.col.find_one(
            {'guild': guild_id, 'tags.name': name.lower()},
            {'_id': 0, 'guild': 1, 'tags.$': 1}
        )
        if ret is None:
            if await self.col.find_one({'guild': guild_id}) is None:
                await self.col.insert_one({'guild': guild_id, 'tags': []})
        return ret

    async def _create_tag(self, ctx: GuildContext, name: str, content: str) -> None:
        await self.col.update_one(
            {'guild': ctx.guild.id},
            {'$push': {'tags': {
                'name': name.lower(), 'content': content, 'uses': 0, 'owner_id': ctx.author.id, 'created_at': ctx.message.created_at
            }}}
        )

    async def _create_alias(self, ctx: GuildContext, new_name: str, old_name: str) -> None:
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

    async def transfer_tag(self, tag: Tag | TagAlias, owner_id: int) -> None:
        await self.col.update_one(
            {'guild': tag.guild_id, 'tags.name': tag.name},
            {'$set': {'tags.$.owner_id': owner_id}}
        )

    def get_tag_list(self, guild_id: int, member_id: int | None) -> list[Tag | TagAlias]:
        if member_id is not None:
            tag_list = [tag for tag in self.cache.get(
                guild_id, {}).values() if tag.owner_id == member_id]
        else:
            tag_list = list(self.cache.get(guild_id, {}).values())
        if not tag_list:
            location = 'for that user' if member_id else 'in that guild'
            raise TagError(f'No tags found {location}.')
        return tag_list

    async def _get_tag(self, guild_id: int, name: str) -> Tag | TagAlias | None:
        if guild_id not in self.cache:
            self.cache[guild_id] = {}
            if await self.col.find_one({'guild': guild_id}) is None:
                await self.col.insert_one({'guild': guild_id, 'tags': []})
            return None
        return self.cache.get(guild_id, {}).get(name, None)

    @overload
    async def get_tag(self, guild_id: int, name: str, *, no_alias: bool = False, return_alias: Literal[False] = False) -> Tag:
        ...

    @overload
    async def get_tag(self, guild_id: int, name: str, *, no_alias: bool = False, return_alias: Literal[True] = True) -> Tag | TagAlias:
        ...

    async def get_tag(self, guild_id: int, name: str, *, no_alias: bool = False, return_alias: bool = False) -> Tag | TagAlias:
        tag: Tag | TagAlias | None = await self._get_tag(guild_id, name)
        if tag is None:
            raise TagError('Tag not found.')
        if isinstance(tag, TagAlias):
            if (main_tag := await self._get_tag(tag.guild_id, tag.alias)) is None:
                await self.delete_tag(Tag.minimal(name, guild_id))
                await self.cache_tags()
                raise TagError('Tag not found.')
            if no_alias:
                raise TagError('You may not edit an alias.')
            if not return_alias:
                return main_tag
        return tag

    async def create_tag(self, ctx: GuildContext, name: str, content: str) -> None:
        if await self._get_tag(ctx.guild.id, name):
            raise TagError(f'A tag with the name "{name}" already exists.')
        await self._create_tag(ctx, name, content)
        await ctx.reply(f'Tag "{name}" successfully created.')

    async def create_alias(self, ctx: GuildContext, new_name: str, old_name: str) -> None:
        if await self._get_tag(ctx.guild.id, new_name):
            raise TagError(f'A tag with the name "{new_name}" already exists.')
        if (tag := await self._get_tag(ctx.guild.id, old_name)) is None:
            raise TagError(
                f'A tag with the name "{old_name}" does not exist.')
        else:
            if isinstance(tag, TagAlias):
                raise TagError('Cannot link an alias to another alias.')
        await self._create_alias(ctx, new_name, old_name)
        await ctx.reply(f'Tag alias "{new_name}" that points to "{old_name}" successfully created.')

    @staticmethod
    def is_privileged(ctx: GuildContext, tag: Tag | TagAlias) -> None:
        author = ctx.author
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
    async def _cache(self, ctx: GuildContext) -> None:
        await self.cache_tags()
        await ctx.reply('Cache updated.')

    @app_commands.command(name='t', description='Gets and shows the tag with the given name.')
    @app_commands.guild_only()
    @app_commands.describe(name='The name of the tag you want to see.')
    async def t(self, inter: discord.Interaction, name: str) -> None:
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

    @commands.hybrid_group(name='tag', aliases=['t'], description='Gets and shows the tag with the given name.', fallback='get')
    @app_commands.guild_only()
    @app_commands.describe(name='The name of the tag you want to see.')
    async def tag(self, ctx: GuildContext, *, name: Annotated[str, TagName]):
        tag = await self.get_tag(ctx.guild.id, name)

        await ctx.reply(tag.content)

        # update the usage
        await self.used_tag(tag)

    @tag.command(name='create', aliases=['make'], description='Creates a new tag with the given name and content.')
    @app_commands.guild_only()
    @app_commands.describe(name='The name of the new tag you want to create.', content='The content of the tag.')
    async def _create(self, ctx: GuildContext, name: Annotated[str, TagName], *, content: Annotated[str, commands.clean_content]):
        if len(content) > 2000:
            return await ctx.send('Tag content is a maximum of 2000 characters.')

        await self.create_tag(ctx, name, content)
        await self.cache_tags()

    @tag.command(name='alias', description='Creates an alias tag that points to another tag.')
    @app_commands.guild_only()
    @app_commands.describe(new_name='The name of the alias.', old_name='The name of the tag you want to refer to.')
    async def _alias(self, ctx: GuildContext, new_name: Annotated[str, TagName], *, old_name: Annotated[str, TagName]):
        await self.create_alias(ctx, new_name, old_name)
        await self.cache_tags()

    @tag.command(name='edit', description='Edits an existing tag. Aliases may not be edited.')
    @app_commands.guild_only()
    @app_commands.describe(name='The name of the new tag you want to edit.', content='The new content of the tag.')
    async def _edit(self, ctx: GuildContext, name: Annotated[str, TagName], *, content: Annotated[str, commands.clean_content]):
        tag = await self.get_tag(ctx.guild.id, name, no_alias=True)
        self.is_privileged(ctx, tag)

        await self.edit_tag(tag, content)
        await ctx.reply(f'Tag "{name}" successfully edited.')
        await self.cache_tags()

    @tag.command(name='remove', aliases=['delete'], description='Deletes the tag with the given name.')
    @app_commands.guild_only()
    @app_commands.describe(name='The name of the tag you want to remove.')
    async def _remove(self, ctx: GuildContext, name: Annotated[str, TagName]):
        tag = await self.get_tag(ctx.guild.id, name, return_alias=True)
        self.is_privileged(ctx, tag)

        await self.delete_tag(tag=tag)
        await ctx.reply(f'Tag "{name}" successfully deleted.')
        await self.cache_tags()

    @tag.command(name='transfer', description='Transfers one of your tags to another member.')
    @app_commands.guild_only()
    @app_commands.describe(member='The member you want to transfer the tag to.', name='The name of the tag you want to transfer.')
    async def _transfer(self, ctx: GuildContext, member: discord.Member, *, name: Annotated[str, TagName]):
        if member.bot:
            raise TagError('You cannot transfer a tag to a bot.')

        tag = await self.get_tag(ctx.guild.id, name, return_alias=True)
        self.is_privileged(ctx, tag)

        await self.transfer_tag(tag, member.id)
        await ctx.reply(f'Successfully transferred tag `{discord.utils.escape_markdown(tag.name)}` to `{member.display_name}`.')
        await self.cache_tags()

    @tag.command(name='info', description='Shows useful information about the tag with the given name.')
    @app_commands.guild_only()
    @app_commands.describe(name='The name of the tag you want to see information about.')
    async def _info(self, ctx: GuildContext, *, name: Annotated[str, TagName]):
        tag = await self.get_tag(ctx.guild.id, name)

        em = discord.Embed(title=tag.name, timestamp=tag.created_at)
        user = self.bot.get_user(tag.owner_id) or (await self.bot.fetch_user(tag.owner_id))
        em.set_author(name=str(user), icon_url=user.display_avatar.url)
        em.add_field(name='Owner', value=f'<@{tag.owner_id}>')
        em.add_field(name='Uses', value=tag.uses)
        em.set_footer(text='Tag created at (UTC)')

        await ctx.reply(embed=em)

    @tag.command(name='raw')
    @app_commands.guild_only()
    async def _raw(self, ctx: GuildContext, *, name: Annotated[str, TagName]):
        tag = await self.get_tag(ctx.guild.id, name)

        escaped = discord.utils.escape_markdown(tag.content)
        await ctx.safe_send(escaped.replace('<', '\\<'), reference=ctx.message)

    @t.autocomplete('name')
    @tag.autocomplete('name')
    @_alias.autocomplete('old_name')
    @_info.autocomplete('name')
    @_raw.autocomplete('name')
    async def t_name_autocomplete(self, inter: Interaction, current: str) -> list[app_commands.Choice[str]]:
        lower = current.lower()
        tags = self.cache.get(inter.guild.id, {}).keys()  # type: ignore
        return create_choices({i for i in tags if lower in i})

    @_edit.autocomplete('name')
    @_remove.autocomplete('name')
    async def t_edit_autocomplete(self, inter: Interaction, current: str) -> list[app_commands.Choice[str]]:
        lower = current.lower()
        return create_choices({
            name for name, tag in self.cache.get(inter.guild.id, {}).items()  # type: ignore # nopep8
            if tag.owner_id == inter.user.id and lower in name
        })

    @tag.command(name='list', description='Shows a list of tags available in this server.')
    @app_commands.guild_only()
    async def _list(self, ctx: GuildContext, *, member: discord.Member | None = None):
        member_id = member.id if member is not None else None
        name = member.name if member is not None else ctx.guild.name
        tag_list = self.get_tag_list(ctx.guild.id, member_id)

        await Paginator(TagSource(tag_list, name, ctx.author)).start(ctx)


async def setup(bot: Advinas):
    await bot.add_cog(Tags(bot))
