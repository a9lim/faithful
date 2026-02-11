"""Chat cog — handles message responses and random replies."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from faithy.bot import Faithy

log = logging.getLogger("faithy.chat")

# How long to wait for more messages before responding (seconds)
DEBOUNCE_DELAY = 3.0


class Chat(commands.Cog):
    """Listens to messages and responds in-character."""

    def __init__(self, bot: Faithy) -> None:
        self.bot = bot
        # Tracks pending debounce tasks per channel: {channel_id: asyncio.Task}
        self._pending: dict[int, asyncio.Task] = {}

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

    async def _debounced_respond(self, channel: discord.abc.Messageable, channel_id: int) -> None:
        """Wait for the debounce period, then generate and send a response.

        If cancelled (because a new message arrived), this coroutine exits silently.
        """
        try:
            await asyncio.sleep(DEBOUNCE_DELAY)
        except asyncio.CancelledError:
            return
        finally:
            # Clean up our entry regardless
            self._pending.pop(channel_id, None)

        # Re-fetch history AFTER the debounce wait so we capture all messages
        # the user sent during the wait period.
        try:
            history_msgs = []
            async for msg in channel.history(limit=20):
                history_msgs.append(msg)
            history_msgs.reverse()

            # Context Slicing: Find the last explicit ping (non-reply mention)
            start_index = 0
            for i, msg in enumerate(history_msgs):
                if self.bot.user in msg.mentions and msg.reference is None:
                    start_index = i
            history_msgs = history_msgs[start_index:]

            # The most recent non-bot message is the "prompt"
            # Find the last user message in history to use as the prompt
            prompt_msg = None
            for msg in reversed(history_msgs):
                if msg.author != self.bot.user and not msg.author.bot:
                    prompt_msg = msg
                    break

            if prompt_msg is None:
                return

            # Build structured context (everything except the prompt message)
            context_for_backend = []
            for m in history_msgs:
                if m.id == prompt_msg.id:
                    continue

                if m.author == self.bot.user:
                    context_for_backend.append({
                        "role": "assistant",
                        "content": m.content
                    })
                else:
                    context_for_backend.append({
                        "role": "user",
                        "content": self._format_msg(m)
                    })

            async with channel.typing():
                response = await self.bot.backend.generate(
                    prompt=prompt_msg.content,
                    examples=self.bot.store.get_all_text(),
                    recent_context=context_for_backend,
                )

            if response:
                # Normalize legacy <SPLIT> to newlines (just in case)
                response = response.replace("<SPLIT>", "\n")

                # Split by newlines
                parts = response.split("\n")

                for part in parts:
                    part = part.strip()
                    if not part:
                        continue

                    # Safety Check 1: Enforce Discord's 2000 char limit
                    chunks = []
                    while len(part) > 2000:
                        split_idx = part.rfind(" ", 0, 2000)
                        if split_idx == -1:
                            split_idx = 2000
                        chunks.append(part[:split_idx])
                        part = part[split_idx:].strip()
                    chunks.append(part)

                    for i, chunk in enumerate(chunks):
                        # Safety Check 2: Ensure ALL chunks end with sentence terminator
                        valid_endings = ('.', '!', '?', '~', '"', ')', '*', '>', ']', '}')
                        if not chunk.endswith(valid_endings):
                            last_punc = -1
                            for punc in valid_endings:
                                idx = chunk.rfind(punc)
                                if idx > last_punc:
                                    last_punc = idx

                            if last_punc != -1:
                                chunk = chunk[:last_punc+1]

                        if chunk:
                            await channel.send(chunk)

                            # Dynamic delay based on message length to simulate typing
                            base_delay = 0.3 + len(chunk) * 0.02
                            delay = base_delay + random.uniform(-0.3, 0.5)
                            delay = max(0.3, min(delay, 3.0))
                            await asyncio.sleep(delay)

        except Exception:
            log.exception("Failed to generate response")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        # Ignore own messages and other bots
        if message.author == self.bot.user or message.author.bot:
            return

        # Check if we have any examples to work with
        if self.bot.store.count == 0:
            return

        # Quick history fetch to decide whether to respond
        history_msgs = []
        async for msg in message.channel.history(limit=20):
            history_msgs.append(msg)
        history_msgs.reverse()

        # Context Slicing
        start_index = 0
        for i, msg in enumerate(history_msgs):
            if self.bot.user in msg.mentions and msg.reference is None:
                start_index = i
        history_msgs = history_msgs[start_index:]

        # Check conversation status
        in_conversation = False
        if len(history_msgs) >= 2:
            prev_msg = history_msgs[-2]
            if prev_msg.author == self.bot.user:
                in_conversation = True

        # Decide whether to respond
        is_dm = message.guild is None
        should_respond = is_dm or in_conversation or self._is_mentioned(message) or self._should_reply_randomly()

        if not should_respond:
            return

        # Debounce: cancel any existing pending response for this channel
        # and start a new timer. This lets the user send multiple messages
        # before the bot responds.
        channel_id = message.channel.id
        existing = self._pending.get(channel_id)
        if existing and not existing.done():
            existing.cancel()

        task = asyncio.create_task(
            self._debounced_respond(message.channel, channel_id)
        )
        self._pending[channel_id] = task


async def setup(bot: Faithy) -> None:
    await bot.add_cog(Chat(bot))
