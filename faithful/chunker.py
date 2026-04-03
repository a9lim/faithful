"""Message delivery — send LLM responses with typing indicators."""

from __future__ import annotations

import re
from collections.abc import AsyncGenerator

import discord


_REACTION_PATTERN = re.compile(r"\[react:\s*([^\]]+)\]")

_MAX_MSG_LEN = 2000


def _chunk_text(text: str) -> list[str]:
    """Split text into Discord-safe chunks (<= 2000 chars).

    Splitting priority: newlines -> sentence ends -> spaces -> hard cut.
    """
    if len(text) <= _MAX_MSG_LEN:
        return [text]

    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= _MAX_MSG_LEN:
            chunks.append(remaining)
            break

        # Try sentence boundary
        split_idx = -1
        for punc in (". ", "! ", "? "):
            idx = remaining.rfind(punc, 0, _MAX_MSG_LEN - 100)
            if idx > split_idx:
                split_idx = idx + 1

        # Try space
        if split_idx <= 0:
            split_idx = remaining.rfind(" ", 0, _MAX_MSG_LEN - 100)

        # Hard cut
        if split_idx <= 0:
            split_idx = _MAX_MSG_LEN

        chunks.append(remaining[:split_idx].strip())
        remaining = remaining[split_idx:].strip()

    return chunks


def extract_reactions(text: str) -> tuple[str, list[str]]:
    """Strip [react: emoji] markers from text and return (clean_text, reactions)."""
    reactions = _REACTION_PATTERN.findall(text)
    clean = _REACTION_PATTERN.sub("", text).strip()
    return clean, [r.strip() for r in reactions if r.strip()]


async def send_responses(
    channel: discord.abc.Messageable,
    responses: AsyncGenerator[str, None],
    react_target: discord.Message | None = None,
    reply_to: discord.Message | None = None,
) -> None:
    """Send each yielded response as a separate message.

    The first chunk replies to *reply_to* if provided. Subsequent chunks
    are sent as standalone messages. Reactions are collected from all
    messages and applied to *react_target*.
    """
    all_reactions: list[str] = []
    first_sent = False

    async for raw_text in responses:
        clean, reactions = extract_reactions(raw_text)
        all_reactions.extend(reactions)
        if clean:
            for chunk in _chunk_text(clean):
                if not first_sent and reply_to:
                    await reply_to.reply(chunk)
                    first_sent = True
                else:
                    await channel.send(chunk)
                    first_sent = True

    if react_target and all_reactions:
        for emoji in all_reactions:
            try:
                await react_target.add_reaction(emoji)
            except discord.DiscordException:
                pass
