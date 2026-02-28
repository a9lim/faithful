"""Prompt assembly — builds a GenerationRequest from channel state."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from .backends.base import GenerationRequest

if TYPE_CHECKING:
    from .bot import Faithful


def format_system_prompt(
    template: str, persona_name: str, examples: list[str]
) -> str:
    """Format a system prompt template with persona name and examples."""
    return template.format(name=persona_name, examples="\n".join(examples))


def build_context(
    history: list[discord.Message],
    bot_user: discord.User | discord.Member,
) -> list[dict[str, str]]:
    """Convert Discord message history to role/content dicts."""
    context: list[dict[str, str]] = []
    for m in history:
        if m.author == bot_user:
            context.append({"role": "assistant", "content": m.content})
        else:
            context.append({
                "role": "user",
                "content": f"{m.author.display_name}: {m.content}",
            })
    return context


def find_prompt_message(
    history: list[discord.Message],
    bot_user: discord.User | discord.Member,
) -> discord.Message | None:
    """Find the most recent non-bot message in history."""
    for msg in reversed(history):
        if msg.author != bot_user and not msg.author.bot:
            return msg
    return None


def slice_from_last_mention(
    history: list[discord.Message],
    bot_user: discord.User | discord.Member,
) -> list[discord.Message]:
    """Trim history to start from the last direct @mention of the bot."""
    start = 0
    for i, msg in enumerate(history):
        if bot_user in msg.mentions and msg.reference is None:
            start = i
    return history[start:]


async def build_request(
    channel: discord.abc.Messageable,
    bot: Faithful,
) -> tuple[GenerationRequest, discord.Message | None]:
    """Assemble a GenerationRequest from current channel state.

    Returns the request and the prompt message (if any) for error reactions.
    """
    limit = bot.config.max_context_messages
    history_msgs: list[discord.Message] = []
    async for msg in channel.history(limit=limit):
        history_msgs.append(msg)
    history_msgs.reverse()

    history_msgs = slice_from_last_mention(history_msgs, bot.user)

    prompt_msg = find_prompt_message(history_msgs, bot.user)
    prompt_content = prompt_msg.content if prompt_msg else ""

    # Build context from everything before the prompt message
    context_msgs: list[discord.Message] = []
    if prompt_msg:
        for m in history_msgs:
            if m.id == prompt_msg.id:
                break
            context_msgs.append(m)
    else:
        context_msgs = history_msgs

    context = build_context(context_msgs, bot.user)
    sampled = bot.store.get_sampled_messages(bot.config.sample_size)

    system_prompt = format_system_prompt(
        bot.config.system_prompt, bot.config.persona_name, sampled
    )

    request = GenerationRequest(
        prompt=prompt_content,
        system_prompt=system_prompt,
        context=context,
    )
    return request, prompt_msg
