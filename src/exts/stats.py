from __future__ import annotations

# std
import io
import json
from typing import Any, TYPE_CHECKING

# packages
import discord
from discord.ext import commands

# local
from common.custom import (
    Context,
)

if TYPE_CHECKING:
    from bot import Advinas
    from motor.motor_asyncio import AsyncIOMotorCollection


class Stats(commands.Cog):
    def __init__(self, bot: Advinas) -> None:
        self.bot = bot
        bot.loop.create_task(self.ready())

    async def ready(self) -> None:
        await self.bot.wait_until_ready()
        self.col: AsyncIOMotorCollection = self.bot.DB.messages

    async def _add_channel(self, data: dict[str, Any]) -> None:
        await self.col.insert_one(data)

    async def _add_message(self, channel_id: int, data: dict[str, Any]) -> None:
        await self.col.update_one(
            {'_id': channel_id},
            {'$push': {'messages': data}}
        )

    def _parse_message(self, message: discord.Message, *, dt_obj: bool = True) -> dict[str, Any]:
        author = message.author
        data = {
            "id": message.id,
            "bot": author.bot,
            "activity": True if message.activity is not None else False,
            "attachments_count": len(message.attachments),
            "author": {
                "id": author.id,
                "name": author.name,
                "discriminator": author.discriminator,
                "bot": author.bot,
                "system": author.system
            },
            "channel_mentions": [{
                "id": channel_mention.id,
                "name": channel_mention.name,
                "category": channel_mention.category.name if channel_mention.category else None,
                "thread": isinstance(channel_mention, discord.Thread),
            } for channel_mention in message.channel_mentions],
            "channel_mentions_count": len(message.channel_mentions),
            "clean_content": message.clean_content,
            "components_count": len(message.components),
            "content": message.content,
            "created_at": message.created_at if dt_obj else message.created_at.isoformat(),
            "edited_at": message.edited_at if message.edited_at is None or dt_obj else message.edited_at.isoformat(),
            "embeds_count": len(message.embeds),
            "jump_url": message.jump_url,
            "mention_everyone": message.mention_everyone,
            "mentions": [{
                "id": mention.id,
                "name": mention.name,
                "discriminator": mention.discriminator,
                "bot": mention.bot,
                "system": mention.system
            } for mention in message.mentions],
            "mentions_count": len(message.mentions),
            "pinned": message.pinned,
            "raw_channel_mentions": message.raw_channel_mentions,
            "raw_mentions": message.raw_mentions,
            "raw_role_mentions": message.raw_role_mentions,
            "reactions": [{
                "count": reaction.count,
                "name": reaction.emoji.name if not isinstance(reaction.emoji, str) else reaction.emoji
            } for reaction in message.reactions],
            "reactions_count": len(message.reactions),
            "reference": True if message.reference is not None else False,
            "role_mentions": [{
                "id": role_mention.id,
                "name": role_mention.name,
            } for role_mention in message.role_mentions],
            "role_mentions_count": len(message.role_mentions),
            "stickers": [{
                "id": sticker.id,
                "name": sticker.name,
            } for sticker in message.stickers],
            "stickers_count": len(message.stickers),
            "system": message.is_system(),
            "system_content": message.system_content,
            "webhook": bool(message.webhook_id),
        }
        return data

    async def _fetch_messages(self, channel: discord.TextChannel, *, dt_obj: bool = True) -> dict[str, Any]:
        count, channel_id, messages = 0, channel.id, []
        async for message in channel.history(limit=None, oldest_first=True):
            messages.append(self._parse_message(message, dt_obj=dt_obj))
            count += 1
            if count % 1e3 == 0:
                print(channel_id, f'{count=}')
        data = {
            "_id": channel_id,
            "category": channel.category.name if channel.category else None,
            "messages": messages,
            "messages_count": len(messages),
            "name": channel.name,
        }
        return data

    # @commands.Cog.listener('on_message')
    # async def _message_listener(self, message: discord.Message) -> None:
    #     if not (message.guild and message.guild.id == 590288287864848387):
    #         return

    #     data = self._parse_message(message)
    #     await self._add_message(message.channel.id, data)

    @commands.command(name='history')
    @commands.is_owner()
    async def history(self, ctx: Context, channel: discord.TextChannel) -> None:
        async with ctx.typing():
            data = await self._fetch_messages(channel, dt_obj=False)
            buffer = io.StringIO()
            json.dump(data, buffer)
            buffer.seek(0)
            file = discord.File(
                filename=f'{channel.id}.json', fp=buffer)  # type: ignore
            await ctx.send(file=file)

    @commands.command(name='fetchall')
    @commands.is_owner()
    async def _fetch_all(self, ctx: Context) -> None:
        guild = ctx.bot.get_guild(590288287864848387)
        assert guild
        async with ctx.typing():
            for channel in guild.text_channels:
                data = await self._fetch_messages(channel)
                await self._add_channel(data)
                await ctx.reply(f'Finished channel `{channel.name}`')
            await ctx.reply('Done')


async def setup(bot: Advinas):
    await bot.add_cog(Stats(bot))
