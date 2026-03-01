"""Prompt assembly — builds a GenerationRequest from channel state."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from .backends.base import Attachment, GenerationRequest

if TYPE_CHECKING:
    from .bot import Faithful
    from .memory import MemoryStore


def format_system_prompt(
    template: str,
    persona_name: str,
    examples: list[str],
    memories: str = "",
    custom_emojis: str = "",
) -> str:
    """Format a system prompt template with persona name, examples, and memories."""
    return template.format(
        name=persona_name,
        examples="\n".join(examples),
        memories=memories,
        custom_emojis=custom_emojis,
    )


def get_guild_emojis(guild: discord.Guild | None) -> str:
    """Build a string listing available custom emoji for the system prompt."""
    if not guild or not guild.emojis:
        return ""
    names = [f":{e.name}:" for e in guild.emojis if e.available]
    if not names:
        return ""
    return f"Available custom emojis in this server: {', '.join(names)}\n"


def format_memories(
    memory_store: MemoryStore,
    channel_id: int,
    participants: dict[int, str],
) -> str:
    """Build formatted memory sections for the system prompt."""
    sections: list[str] = []

    # User memories
    for user_id, display_name in participants.items():
        _, facts = memory_store.get_user_memories(user_id)
        if facts:
            lines = "\n".join(f"- {f}" for f in facts)
            sections.append(f"What you know about {display_name}:\n{lines}")

    # Channel memories
    channel_mems = memory_store.get_channel_memories(channel_id)
    if channel_mems:
        lines = "\n".join(f"- {m}" for m in channel_mems)
        sections.append(f"What you know about this channel:\n{lines}")

    if not sections:
        return ""

    return "\n".join(sections) + "\n\n"


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
    limit = bot.config.max_context_messages
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
    sampled = bot.store.get_sampled_messages(bot.config.sample_size)

    # Build memory text if enabled
    memories = ""
    channel_id = 0
    if hasattr(channel, "id"):
        channel_id = channel.id  # type: ignore[union-attr]
    if bot.config.enable_memory and bot.memory_store is not None:
        memories = format_memories(bot.memory_store, channel_id, participants)

    custom_emojis = get_guild_emojis(guild)

    system_prompt = format_system_prompt(
        bot.config.system_prompt, bot.config.persona_name, sampled, memories, custom_emojis
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
