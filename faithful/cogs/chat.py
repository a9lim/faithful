"""Chat cog — handles message responses and random replies."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING

import discord
from discord.ext import commands
from discord.utils import utcnow

from faithful.chunker import send_chunked
from faithful.prompt import build_request

if TYPE_CHECKING:
    from faithful.bot import Faithful

log = logging.getLogger("faithful.chat")


class Chat(commands.Cog):
    """Listens to messages and responds in-character."""

    def __init__(self, bot: Faithful) -> None:
        self.bot = bot
        self._pending: dict[int, asyncio.Task] = {}

    def _should_reply_randomly(self) -> bool:
        return random.random() < self.bot.config.reply_probability

    def _is_mentioned(self, message: discord.Message) -> bool:
        if self.bot.user is None:
            return False
        if self.bot.user.mentioned_in(message):
            return True
        if message.reference and message.reference.resolved:
            ref = message.reference.resolved
            if isinstance(ref, discord.Message) and ref.author == self.bot.user:
                age = (utcnow() - ref.created_at).total_seconds()
                return age < self.bot.config.conversation_expiry
        return False

    async def _debounced_respond(
        self, channel: discord.abc.Messageable, channel_id: int
    ) -> None:
        try:
            async with channel.typing():
                await asyncio.sleep(self.bot.config.debounce_delay)

            request, prompt_msg = await build_request(channel, self.bot)
            response = await self.bot.backend.generate(request)

            if response:
                await send_chunked(channel, response)
            elif prompt_msg:
                try:
                    await prompt_msg.add_reaction("\u26a0\ufe0f")
                except discord.DiscordException:
                    pass

        except asyncio.CancelledError:
            return
        except Exception:
            log.exception("Failed to generate response")
        finally:
            self._pending.pop(channel_id, None)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.bot.user or message.author.bot:
            return

        if self.bot.store.count == 0:
            return

        is_dm = message.guild is None
        is_mentioned = self._is_mentioned(message)

        in_conversation = False
        if not (is_mentioned or is_dm):
            history: list[discord.Message] = []
            async for m in message.channel.history(limit=7):
                history.append(m)

            if len(history) >= 2:
                for prev_msg in history[1:]:
                    if prev_msg.author == self.bot.user:
                        age = (utcnow() - prev_msg.created_at).total_seconds()
                        if age < self.bot.config.conversation_expiry:
                            in_conversation = True
                        break

        if not (is_dm or is_mentioned or in_conversation or self._should_reply_randomly()):
            return

        channel_id = message.channel.id
        existing = self._pending.get(channel_id)
        if existing and not existing.done():
            existing.cancel()

        task = asyncio.create_task(
            self._debounced_respond(message.channel, channel_id)
        )
        self._pending[channel_id] = task


async def setup(bot: Faithful) -> None:
    await bot.add_cog(Chat(bot))
