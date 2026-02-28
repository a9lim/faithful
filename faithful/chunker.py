"""Message delivery — chunk text and send with typing delays."""

from __future__ import annotations

import asyncio
import random

import discord


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


async def send_chunked(channel: discord.abc.Messageable, text: str) -> None:
    """Chunk *text* and send each piece with a typing indicator."""
    for chunk in chunk_response(text):
        async with channel.typing():
            await asyncio.sleep(typing_delay(chunk))
            await channel.send(chunk)
