"""Message delivery — chunk text and send with typing delays."""

from __future__ import annotations

import asyncio
import random
import re

import discord


_REACTION_PATTERN = re.compile(r"\[react:\s*([^\]]+)\]")


def extract_reactions(text: str) -> tuple[str, list[str]]:
    """Strip [react: emoji] markers from text and return (clean_text, reactions)."""
    reactions = _REACTION_PATTERN.findall(text)
    clean = _REACTION_PATTERN.sub("", text).strip()
    return clean, [r.strip() for r in reactions if r.strip()]


def chunk_response(text: str) -> list[str]:
    """Split text into Discord-safe chunks (<= 2000 chars).

    Splitting priority: newlines -> sentence ends -> spaces -> hard cut.
    """
    chunks: list[str] = []

    for paragraph in text.split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        remaining = paragraph
        while remaining:
            if len(remaining) <= 2000:
                chunks.append(remaining)
                break

            # Try sentence boundary
            split_idx = -1
            for punc in (". ", "! ", "? "):
                idx = remaining.rfind(punc, 0, 1900)
                if idx > split_idx:
                    split_idx = idx + 1  # include the punctuation

            # Try space
            if split_idx <= 0:
                split_idx = remaining.rfind(" ", 0, 1900)

            # Hard cut
            if split_idx <= 0:
                split_idx = 2000

            chunks.append(remaining[:split_idx].strip())
            remaining = remaining[split_idx:].strip()

    return chunks


def typing_delay(text: str) -> float:
    """Calculate a simulated typing delay for *text* (~15 chars/sec)."""
    base = 0.8 + len(text) / 15.0
    delay = base + random.uniform(-0.3, 0.5)
    return max(1.0, min(delay, 5.0))


async def send_chunked(
    channel: discord.abc.Messageable,
    text: str,
    react_target: discord.Message | None = None,
) -> None:
    """Chunk *text* and send each piece with a typing indicator."""
    clean_text, reactions = extract_reactions(text)

    for chunk in chunk_response(clean_text):
        async with channel.typing():
            await asyncio.sleep(typing_delay(chunk))
            await channel.send(chunk)

    if react_target and reactions:
        for emoji in reactions:
            try:
                await react_target.add_reaction(emoji)
            except discord.DiscordException:
                pass
