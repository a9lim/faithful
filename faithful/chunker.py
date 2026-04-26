"""Message delivery — send LLM responses with typing indicators.

Multi-message intent comes from the model calling the ``continue`` tool: each
generator yield is sent as a single Discord message. The model is responsible
for shaping its messages -- newlines stay intact and never trigger a split.

The hard 2000-character Discord limit is the only thing that can force a
single yield to be broken into multiple sends. ``_split_oversized`` is a
last-resort fallback for that case.
"""

from __future__ import annotations

import re
from collections.abc import AsyncGenerator

import discord


_REACTION_PATTERN = re.compile(r"\[react:\s*([^\]]+)\]")

_MAX_MSG_LEN = 2000


def _split_oversized(text: str) -> list[str]:
    """Fallback splitter for text that exceeds Discord's 2000-char ceiling.

    Only invoked when a single yielded message is too long to send as-is.
    Tries to break on a sentence boundary, then on a space, then hard-cuts.
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
    """Send each yielded response as a separate Discord message.

    Each ``yield`` from *responses* maps to one Discord message — the model
    drives multi-message behavior via the ``continue`` tool. Newlines inside
    a yielded chunk are preserved.

    The first message replies to *reply_to* if provided; subsequent ones are
    standalone. Reactions are collected from all messages and applied to
    *react_target*. The 2000-char Discord limit is enforced as a fallback;
    callers shouldn't rely on it.
    """
    all_reactions: list[str] = []
    first_sent = False

    async for raw_text in responses:
        clean, reactions = extract_reactions(raw_text)
        all_reactions.extend(reactions)
        if not clean:
            continue

        # Normal path: one yield = one message. Only split if the model
        # produced something larger than Discord allows in a single send.
        pieces = [clean] if len(clean) <= _MAX_MSG_LEN else _split_oversized(clean)

        for piece in pieces:
            if not first_sent and reply_to:
                await reply_to.reply(piece)
            else:
                await channel.send(piece)
            first_sent = True

    if react_target and all_reactions:
        for emoji in all_reactions:
            try:
                await react_target.add_reaction(emoji)
            except discord.DiscordException:
                pass
