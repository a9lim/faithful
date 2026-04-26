"""Tests for the onboarding cog."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from faithful.cogs.onboarding import Onboarding


@pytest.fixture
def fake_bot(tmp_path):
    bot = MagicMock()
    bot.config = MagicMock()
    bot.config.data_dir = tmp_path
    bot.config.discord = MagicMock()
    bot.config.discord.admin_ids = [42]
    return bot


@pytest.mark.asyncio
async def test_dm_sent_on_first_join(fake_bot):
    cog = Onboarding(fake_bot)

    admin_user = MagicMock()
    admin_user.send = AsyncMock()
    fake_bot.get_user.return_value = admin_user

    guild = MagicMock(spec=discord.Guild)
    guild.id = 1234
    guild.name = "MyGuild"
    guild.text_channels = []

    await cog.on_guild_join(guild)

    admin_user.send.assert_called_once()
    args = admin_user.send.call_args[0]
    assert "MyGuild" in args[0]


@pytest.mark.asyncio
async def test_no_resend_after_restart(fake_bot, tmp_path):
    seen_path = tmp_path / "seen_guilds.json"
    seen_path.write_text(json.dumps([1234]))

    cog = Onboarding(fake_bot)

    admin_user = MagicMock()
    admin_user.send = AsyncMock()
    fake_bot.get_user.return_value = admin_user

    guild = MagicMock(spec=discord.Guild)
    guild.id = 1234
    guild.name = "MyGuild"
    guild.text_channels = []

    await cog.on_guild_join(guild)

    admin_user.send.assert_not_called()


@pytest.mark.asyncio
async def test_falls_back_to_channel_on_forbidden(fake_bot):
    cog = Onboarding(fake_bot)

    admin_user = MagicMock()
    admin_user.send = AsyncMock(
        side_effect=discord.Forbidden(MagicMock(), "DMs disabled")
    )
    fake_bot.get_user.return_value = admin_user

    chan = MagicMock(spec=discord.TextChannel)
    chan.send = AsyncMock()
    perms = MagicMock()
    perms.send_messages = True
    chan.permissions_for.return_value = perms

    guild = MagicMock(spec=discord.Guild)
    guild.id = 1234
    guild.name = "MyGuild"
    guild.text_channels = [chan]
    guild.me = MagicMock()

    await cog.on_guild_join(guild)

    chan.send.assert_called_once()
    msg = chan.send.call_args[0][0]
    assert "<@42>" in msg
    assert "MyGuild" in msg
