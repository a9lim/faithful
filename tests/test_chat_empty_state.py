"""Tests for the empty-corpus reply behaviour in chat.py."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from faithful.cogs.chat import EMPTY_STATE_TEXT, Chat


@pytest.mark.asyncio
async def test_replies_with_empty_state_when_pinged_and_corpus_empty():
    bot = MagicMock()
    bot.user = MagicMock()
    bot.store.count = 0
    bot.config.behavior.reply_probability = 0.0
    bot.config.behavior.conversation_expiry = 300

    cog = Chat(bot)

    msg = MagicMock()
    msg.author = MagicMock()
    msg.author.bot = False
    msg.guild = MagicMock()
    msg.reply = AsyncMock()
    bot.user.mentioned_in.return_value = True
    msg.reference = None
    msg.channel = MagicMock()

    await cog.on_message(msg)

    msg.reply.assert_awaited_once_with(EMPTY_STATE_TEXT)


@pytest.mark.asyncio
async def test_silent_when_random_trigger_and_corpus_empty():
    bot = MagicMock()
    bot.user = MagicMock()
    bot.store.count = 0
    bot.config.behavior.reply_probability = 1.0  # would trigger if corpus existed
    bot.config.behavior.conversation_expiry = 300

    cog = Chat(bot)

    msg = MagicMock()
    msg.author = MagicMock()
    msg.author.bot = False
    msg.guild = MagicMock()
    msg.reply = AsyncMock()
    bot.user.mentioned_in.return_value = False
    msg.reference = None
    msg.channel = MagicMock()
    # No history that contains the bot
    async def empty_history(limit):
        if False:
            yield
    msg.channel.history = MagicMock(return_value=empty_history(7))

    await cog.on_message(msg)

    msg.reply.assert_not_awaited()
