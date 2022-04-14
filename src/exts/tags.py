# std
from typing import Optional

# packages
import discord
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorCollection

# local
from bot import Advinas
from common.custom import Context, Tag, TagName, TagError


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

    # declare group commands
    # tag_group = app_commands.Group(
    #     name="tag",
    #     description="Shows tags and allows for useful utility."
    # )

    async def cog_check(self, ctx: Context) -> bool:
        return ctx.guild is not None

    async def cog_command_error(self, ctx: Context, err: Exception) -> None:
        if isinstance(err, commands.CommandInvokeError):
            err = err.original
        if isinstance(err, TagError):
            await ctx.reply(err)
            await ctx.log(err)

    async def _get_tag(self, guild_id: int, name: str) -> Optional[dict]:
        if (ret := await self.col.find_one(
            {"guild": guild_id, "tags.name": name.lower()},
            {"_id": 0, "guild": 1, "tags.$": 1}
        )) is None:
            if await self.col.find_one({'guild': guild_id}) is None:
                await self.col.insert_one({'guild': guild_id, 'tags': []})
        return ret

    async def _create_tag(self, ctx: Context, name: str, content: str) -> None:
        await self.col.update_one(
            {'guild': ctx.guild.id},
            {'$push': {'tags': {
                'name': name.lower(), 'content': content, 'uses': 0, 'owner_id': ctx.author.id, 'created_at': ctx.message.created_at.strftime('%c')
            }}}
        )

    async def _create_alias(self, ctx: Context, new_name: str, old_name: str) -> None:
        await self.col.update_one(
            {'guild': ctx.guild.id},
            {'$push': {'tags': {
                'name': new_name.lower(), 'alias': old_name.lower(), 'owner_id': ctx.author.id, 'created_at': ctx.message.created_at.strftime('%c')
            }}}
        )

    async def used_tag(self, tag: Tag) -> None:
        await self.col.update_one({'guild': tag.guild_id, 'tags.name': tag.name}, {'$inc': {'tags.0.uses': 1}})

    async def delete_tag(self, tag: Tag) -> None:
        await self.col.update_one({'guild': tag.guild_id}, {'$pull': {'tags': {'name': tag.name}}})

    async def get_tag(self, guild_id: int, name: str) -> Tag:
        if (res := await self._get_tag(guild_id, name)) is None:
            raise TagError('Tag not found.')
        if (alias := res['tags'][0].get('alias', None)) is not None:
            if (res := await self._get_tag(guild_id, alias)) is None:
                await self.delete_tag(guild_id, name)
                raise TagError('Tag not found.')
        return Tag.from_db(res)

    async def create_tag(self, ctx: Context, name: str, content: str) -> None:
        if await self._get_tag(ctx.guild.id, name):
            raise TagError('A tag with this name already exists.')
        await self._create_tag(ctx, name, content)
        await ctx.log('Tag successfully created.')

    async def create_alias(self, ctx: Context, new_name: str, old_name: str) -> None:
        if await self._get_tag(ctx.guild.id, new_name):
            raise TagError('A tag with this name already exists.')
        if (tag := await self._get_tag(ctx.guild.id, old_name)) is None:
            raise TagError(f'A tag with the name of "{old_name}" does not exist.')  # nopep8
        else:
            if hasattr(tag, 'alias'):
                raise TagError('Cannot link an alias to another alias.')
        await self._create_alias(ctx, new_name, old_name)
        await ctx.reply(f'Tag alias "{new_name}" that points to "{old_name}" successfully created.')

    @staticmethod
    async def can_delete(ctx: Context, tag: Tag) -> None:
        if ctx.author.id != tag.owner_id:
            if not (ctx.author.guild_permissions.manage_guild or ctx.author.guild_permissions.administrator):
                raise TagError('This is not your tag and you do not have the manager server permission.')  # nopep8

    @commands.hybrid_group(name='tag', invoke_without_command=True)
    async def tag(self, ctx: Context, *, name: TagName):
        tag = await self.get_tag(ctx.guild.id, name)

        await ctx.reply(tag.content)
        await ctx.log()

        # update the usage
        await self.used_tag(tag)

    @tag.command(name='create', aliases=['make'])
    async def _create(self, ctx: Context, name: TagName, *, content: commands.clean_content):
        if len(content) > 2000:
            return await ctx.send('Tag content is a maximum of 2000 characters.')

        await self.create_tag(ctx, name, content)

        await ctx.log()

    @tag.command(name='alias')
    async def _alias(self, ctx: Context, new_name: TagName, *, old_name: TagName):
        await self.create_alias(ctx, new_name, old_name)

        await ctx.log()

    @tag.command(name='remove', aliases=['delete'])
    async def _remove(self, ctx: Context, name: TagName):
        tag = await self.get_tag(ctx.guild.id, name)
        await self.can_delete(ctx, tag)

        await self.delete_tag(tag=tag)
        await ctx.reply(f'Tag "{name}" successfully deleted.')
        await ctx.log()

    @tag.command(name='info')
    async def _info(self, ctx: Context, *, name: TagName):
        tag = await self.get_tag(ctx.guild.id, name)

        em = discord.Embed(title=tag.name, timestamp=tag.created_at)
        user = self.bot.get_user(tag.owner_id) or (await self.bot.fetch_user(tag.owner_id))
        em.set_author(name=str(user), icon_url=user.display_avatar.url)
        em.add_field(name='Owner', value=f'<@{tag.owner_id}>')
        em.add_field(name='Uses', value=tag.uses)
        em.set_footer(text='Tag created at')

        await ctx.reply(embed=em)
        await ctx.log()

    # @tag.command(name='search')
    # async def _search(self, ctx, *, query: commands.clean_content):
    #     ...


async def setup(bot: Advinas):
    await bot.add_cog(Tags(bot), guild=discord.Object(796313079708123147))
