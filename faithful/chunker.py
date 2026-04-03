"""Message delivery — send LLM responses with typing indicators."""

from __future__ import annotations

import re
from collections.abc import AsyncGenerator

import discord


_REACTION_PATTERN = re.compile(r"\[react:\s*([^\]]+)\]")


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
            if not first_sent and reply_to:
                await reply_to.reply(clean)
                first_sent = True
            else:
                await channel.send(clean)
                first_sent = True

    if react_target and all_reactions:
        for emoji in all_reactions:
            try:
                await react_target.add_reaction(emoji)
            except discord.DiscordException:
                pass
