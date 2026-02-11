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


class Chat(commands.Cog):
    """Listens to messages and responds in-character."""

    def __init__(self, bot: Faithy) -> None:
        self.bot = bot

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

        # Check if we have any examples to work with
        if self.bot.store.count == 0:
            return

        # Dynamic Context Fetching
        # Fetch the last 20 messages from the channel history
        history_msgs = []
        async for msg in message.channel.history(limit=20):
            history_msgs.append(msg)
        
        # History is returned newest-first, so reverse it
        history_msgs.reverse()

        # Context Slicing: Find the last explicit ping (non-reply mention)
        # This acts as a "start of conversation" marker.
        start_index = 0
        for i, msg in enumerate(history_msgs):
            # Check if this message is an explicit ping to us
            if self.bot.user in msg.mentions and msg.reference is None:
                start_index = i
        
        # Slice history to include only messages from the last ping onwards
        history_msgs = history_msgs[start_index:]

        # Build context strings
        recent_context_strs = [self._format_msg(m) for m in history_msgs]
        
        # Check conversation status (was the last message from us?)
        # We need to look at the message immediately preceding the current one.
        # history_msgs includes the current message at the end.
        in_conversation = False
        if len(history_msgs) >= 2:
            prev_msg = history_msgs[-2]
            if prev_msg.author == self.bot.user:
                in_conversation = True

        # Decide whether to respond
        # Always respond in DMs, or if in active conversation, otherwise check mentions/random chance
        is_dm = message.guild is None
        should_respond = is_dm or in_conversation or self._is_mentioned(message) or self._should_reply_randomly()

        if not should_respond:
            return

        # Generate and send response
        try:
            async with message.channel.typing():
                # Pass the dynamically fetched context
                # Exclude the current message from context if the backend appends it manually, 
                # but backends usually expect 'recent_context' to be the history *before* the prompt.
                # However, the backend implementation adds 'prompt' separately.
                # So we should pass messages *before* the current one as context.
                
                # Filter out the current message from context passed to backend
                # (The backend adds the prompt/current message itself)
                context_for_backend = []
                for m in history_msgs:
                    if m.id == message.id:
                        continue
                    
                    if m.author == self.bot.user:
                        # Our own messages -> Role: assistant
                        context_for_backend.append({
                            "role": "assistant",
                            "content": m.content
                        })
                    else:
                        # Other users -> Role: user
                        # We still format the content to include the name for multi-user context
                        context_for_backend.append({
                            "role": "user",
                            "content": self._format_msg(m)
                        })

                response = await self.bot.backend.generate(
                    prompt=message.content,
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
                    # If a single part is too long, chunk it by whitespace
                    chunks = []
                    while len(part) > 2000:
                        # Find the last whitespace before limit
                        split_idx = part.rfind(" ", 0, 2000)
                        if split_idx == -1:
                            # No whitespace found, hard cut
                            split_idx = 2000
                        chunks.append(part[:split_idx])
                        part = part[split_idx:].strip()
                    chunks.append(part)

                    for i, chunk in enumerate(chunks):
                        # Safety Check 2: Ensure chunk ends with sentence terminator
                        # This prevents cutoff mid-sentence if LLM ran out of tokens
                        # WE ONLY ENFORCE THIS FOR INTERMEDIATE CHUNKS.
                        # The final chunk is allowed to end abruptly (or naturally without punctuation).
                        is_last = (i == len(chunks) - 1)
                        valid_endings = ('.', '!', '?', '~', '"', ')', '*', '>', ']', '}')
                        
                        if not is_last and not chunk.endswith(valid_endings):
                            # Try to find the last valid ending
                            last_punc = -1
                            for punc in valid_endings:
                                idx = chunk.rfind(punc)
                                if idx > last_punc:
                                    last_punc = idx
                            
                            if last_punc != -1:
                                # Cut off everything after the last valid punctuation
                                chunk = chunk[:last_punc+1]
                            # If no punctuation at all, we send as-is (risky but better than empty)

                        if chunk:
                            await message.channel.send(chunk)
                            # We don't need to manually track context anymore since we fetch from history!
                            
                            await asyncio.sleep(1.0) # Small delay between messages

        except Exception:
            log.exception("Failed to generate response")


async def setup(bot: Faithy) -> None:
    await bot.add_cog(Chat(bot))
