"""Prompt assembly — builds a GenerationRequest from channel state."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from .backends.base import Attachment, GenerationRequest

if TYPE_CHECKING:
    from .bot import Faithful


def format_system_prompt(
    template: str,
    persona_name: str,
    examples: list[str],
    custom_emojis: str = "",
    enable_memory: bool = False,
    has_native_memory: bool = False,
) -> str:
    """Format a system prompt template with persona name and examples."""
    prompt = template.format(
        name=persona_name,
        examples="\n".join(examples),
        custom_emojis=custom_emojis,
    )
    # Inject memory protocol for non-Anthropic backends
    if enable_memory and not has_native_memory:
        memory_protocol = (
            "\n\nIMPORTANT: ALWAYS VIEW YOUR MEMORY DIRECTORY BEFORE DOING ANYTHING ELSE.\n"
            "MEMORY PROTOCOL:\n"
            "1. Use the `view` command of your `memory` tool to check for earlier progress.\n"
            "2. As you work, record status / progress / thoughts in your memory.\n"
            "ASSUME INTERRUPTION: Your context window might be reset at any moment.\n"
        )
        prompt += memory_protocol
    return prompt


def get_guild_emojis(guild: discord.Guild | None) -> str:
    """Build a string listing available custom emoji for the system prompt."""
    if not guild or not guild.emojis:
        return ""
    names = [f":{e.name}:" for e in guild.emojis if e.available]
    if not names:
        return ""
    return f"Available custom emojis in this server: {', '.join(names)}\n"



def _attachment_annotations(msg: discord.Message) -> str:
    """Return text annotations for a message's attachments."""
    parts: list[str] = []
    for att in msg.attachments:
        if att.content_type and att.content_type.startswith("image/"):
            parts.append(f"[image: {att.filename}]")
        else:
            parts.append(f"[attached: {att.filename}]")
    return " ".join(parts)


def build_context(
    history: list[discord.Message],
    bot_user: discord.User | discord.Member,
) -> list[dict[str, str]]:
    """Convert Discord message history to role/content dicts."""
    context: list[dict[str, str]] = []
    for m in history:
        content = m.content
        annotations = _attachment_annotations(m)
        if annotations:
            content = f"{content} {annotations}" if content else annotations
        if m.author == bot_user:
            context.append({"role": "assistant", "content": content})
        else:
            context.append({
                "role": "user",
                "content": f"{m.author.display_name}: {content}",
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
    guild: discord.Guild | None = None,
) -> tuple[GenerationRequest, discord.Message | None]:
    """Assemble a GenerationRequest from current channel state.

    Returns the request and the prompt message (if any) for error reactions.
    """
    limit = bot.config.behavior.max_context_messages
    history_msgs: list[discord.Message] = []
    async for msg in channel.history(limit=limit):
        history_msgs.append(msg)
    history_msgs.reverse()

    history_msgs = slice_from_last_mention(history_msgs, bot.user)

    # Collect participants from history
    participants: dict[int, str] = {}
    for m in history_msgs:
        if m.author != bot.user and not m.author.bot:
            participants[m.author.id] = m.author.display_name

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

    # Process attachments on the prompt message
    attachments: list[Attachment] = []
    if prompt_msg:
        for att in prompt_msg.attachments:
            ct = att.content_type or ""
            if ct.startswith("image/"):
                data = await att.read()
                attachments.append(Attachment(att.filename, ct, data))
            elif ct.startswith("text/"):
                data = await att.read()
                text = data.decode("utf-8", errors="replace")
                prompt_content += f"\n[File: {att.filename}]\n{text}"
            else:
                prompt_content += f"\n[Attached file: {att.filename}]"

    context = build_context(context_msgs, bot.user)
    sampled = bot.store.get_sampled_messages(bot.config.llm.sample_size)

    channel_id = 0
    if hasattr(channel, "id"):
        channel_id = channel.id  # type: ignore[union-attr]

    custom_emojis = get_guild_emojis(guild)

    system_prompt = format_system_prompt(
        bot.config.behavior.system_prompt,
        bot.config.behavior.persona_name,
        sampled,
        custom_emojis,
        enable_memory=bot.config.behavior.enable_memory,
        has_native_memory=getattr(bot.backend, '_has_native_memory', False),
    )

    guild_id = guild.id if guild else 0
    request = GenerationRequest(
        prompt=prompt_content,
        system_prompt=system_prompt,
        context=context,
        attachments=attachments,
        channel_id=channel_id,
        guild_id=guild_id,
        participants=participants,
    )
    return request, prompt_msg
