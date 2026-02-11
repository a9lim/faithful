"""Chat cog — handles message responses and random replies."""

from __future__ import annotations

import logging
import random
from collections import defaultdict, deque
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from faithy.bot import Faithy

log = logging.getLogger("faithy.chat")

# Maximum number of recent messages to track per channel for context
CONTEXT_WINDOW = 10


class Chat(commands.Cog):
    """Listens to messages and responds in-character."""

    def __init__(self, bot: Faithy) -> None:
        self.bot = bot
        # channel_id -> deque of recent message strings
        self._context: defaultdict[int, deque[str]] = defaultdict(
            lambda: deque(maxlen=CONTEXT_WINDOW)
        )

    def _format_msg(self, message: discord.Message) -> str:
        """Format a Discord message for context: 'Author: content'."""
        return f"{message.author.display_name}: {message.content}"

    def _should_reply_randomly(self) -> bool:
        """Roll the dice for a random unsolicited reply."""
        return random.random() < self.bot.config.reply_probability

    def _is_mentioned(self, message: discord.Message) -> bool:
        """Check if the bot was mentioned or replied to."""
        if self.bot.user is None:
            return False
        # Direct @mention
        if self.bot.user.mentioned_in(message):
            return True
        # Reply to one of our messages
        if message.reference and message.reference.resolved:
            ref = message.reference.resolved
            if isinstance(ref, discord.Message) and ref.author == self.bot.user:
                return True
        return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        # Ignore own messages and other bots
        if message.author == self.bot.user or message.author.bot:
            return

        # Ignore DMs
        if message.guild is None:
            return

        # Track context
        self._context[message.channel.id].append(self._format_msg(message))

        # Check if we have any examples to work with
        if self.bot.store.count == 0:
            return

        # Decide whether to respond
        should_respond = self._is_mentioned(message) or self._should_reply_randomly()

        if not should_respond:
            return

        # Generate and send response
        try:
            async with message.channel.typing():
                recent = list(self._context[message.channel.id])
                response = await self.bot.backend.generate(
                    prompt=message.content,
                    examples=self.bot.store.get_all_text(),
                    recent_context=recent,
                )

            if response:
                sent = await message.channel.send(response)
                # Track our own message in context
                self._context[message.channel.id].append(
                    self._format_msg(sent)
                )
        except Exception:
            log.exception("Failed to generate response")


async def setup(bot: Faithy) -> None:
    await bot.add_cog(Chat(bot))
