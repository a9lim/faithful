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
# Moved to Config: DEBOUNCE_DELAY


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
                # Only respond if the message being replied to isn't too old
                from discord.utils import utcnow
                age = (utcnow() - ref.created_at).total_seconds()
                return age < self.bot.config.conversation_expiry
        return False

    async def _debounced_respond(self, channel: discord.abc.Messageable, channel_id: int) -> None:
        """Wait for the debounce period, then generate and send a response.

        If cancelled (because a new message arrived), this coroutine exits silently.
        """
        try:
            # Show the bot is thinking/typing early
            async with channel.typing():
                await asyncio.sleep(self.bot.config.debounce_delay)
                
                # Re-fetch history AFTER the debounce wait
                limit = self.bot.config.max_context_messages
                history_msgs = []
                async for msg in channel.history(limit=limit):
                    history_msgs.append(msg)
                history_msgs.reverse()

                # Context Slicing: Find the last explicit ping (non-reply mention)
                start_index = 0
                for i, msg in enumerate(history_msgs):
                    if self.bot.user in msg.mentions and msg.reference is None:
                        start_index = i
                history_msgs = history_msgs[start_index:]

                # The most recent non-bot message is the "prompt"
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

                # Get a balanced sample of examples
                sampled_examples = self.bot.store.get_sampled_messages(
                    self.bot.config.llm_sample_size
                )
                examples_text = "\n".join(sampled_examples)

                response = await self.bot.backend.generate(
                    prompt=prompt_msg.content,
                    examples=examples_text,
                    recent_context=context_for_backend,
                )

                if response:
                    # Normalize legacy <SPLIT> to newlines
                    response = response.replace("<SPLIT>", "\n")

                    # Split by newlines first
                    paragraphs = [p.strip() for p in response.split("\n") if p.strip()]

                    for paragraph in paragraphs:
                        # Split paragraph into sentences or smaller chunks
                        # We want to avoid sending massive blocks of text
                        # but also avoid sending single words if possible.
                        
                        remaining = paragraph
                        while remaining:
                            if len(remaining) <= 2000:
                                chunk = remaining
                                remaining = ""
                            else:
                                # Try splitting at a good point (sentence end)
                                split_idx = -1
                                for punc in ('. ', '! ', '? '):
                                    idx = remaining.rfind(punc, 0, 1900) # Use 1900 to be safe
                                    if idx > split_idx:
                                        split_idx = idx + 1 # Include the punctuation
                                
                                if split_idx == -1:
                                    # Try splitting at a space
                                    split_idx = remaining.rfind(" ", 0, 1900)
                                
                                if split_idx == -1:
                                    # Hard cut at 2000
                                    split_idx = 2000
                                
                                chunk = remaining[:split_idx].strip()
                                remaining = remaining[split_idx:].strip()

                            if chunk:
                                await channel.send(chunk)

                                # Dynamic delay simulated typing
                                # Roughly 150-250 WPM = 2.5-4 words per second
                                # Average word is 5 chars. So 12.5-20 chars per second.
                                # Let's use 15 chars per second average.
                                base_delay = 0.8 + (len(chunk) / 15.0)
                                delay = base_delay + random.uniform(-0.3, 0.5)
                                delay = max(1.0, min(delay, 5.0))
                                await asyncio.sleep(delay)

        except asyncio.CancelledError:
            return
        except Exception:
            log.exception("Failed to generate response")
        finally:
            # Clean up our entry regardless
            self._pending.pop(channel_id, None)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        # Ignore own messages and other bots
        if message.author == self.bot.user or message.author.bot:
            return

        # Check if we have any examples to work with
        if self.bot.store.count == 0:
            return

        # Decide whether to respond
        is_dm = message.guild is None
        is_mentioned = self._is_mentioned(message)
        
        # Optimization: Only fetch history if we weren't mentioned and aren't in a DM
        # (Since we always respond to those anyway)
        in_conversation = False
        if not (is_mentioned or is_dm):
            # Fetch just enough history to check recent conversation flow
            history = []
            async for m in message.channel.history(limit=2):
                history.append(m)
            
            if len(history) >= 2:
                prev_msg = history[1] # The message before current one
                if prev_msg.author == self.bot.user:
                    from discord.utils import utcnow
                    age = (utcnow() - prev_msg.created_at).total_seconds()
                    if age < self.bot.config.conversation_expiry:
                        in_conversation = True

        should_respond = is_dm or is_mentioned or in_conversation or self._should_reply_randomly()

        if not should_respond:
            return

        # Debounce
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
