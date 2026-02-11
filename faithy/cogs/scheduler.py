"""Scheduler cog — sends 1–2 unprompted messages per day at random times."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING

from discord.ext import commands, tasks

if TYPE_CHECKING:
    from faithy.bot import Faithy

log = logging.getLogger("faithy.scheduler")

# Range for random interval between spontaneous messages (in seconds)
# 1–2 messages per day → interval roughly 12–24 hours
MIN_INTERVAL = 12 * 60 * 60  # 12 hours
MAX_INTERVAL = 24 * 60 * 60  # 24 hours


class Scheduler(commands.Cog):
    """Sends unprompted messages to configured channels."""

    def __init__(self, bot: Faithy) -> None:
        self.bot = bot
        self._started = False

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if not self._started:
            self._started = True
            self.spontaneous_loop.start()
            log.info("Spontaneous message scheduler started.")

    def cog_unload(self) -> None:
        self.spontaneous_loop.cancel()

    @tasks.loop(hours=1)  # placeholder interval; we randomise inside
    async def spontaneous_loop(self) -> None:
        # Wait a random interval (12–24h) before sending
        delay = random.uniform(MIN_INTERVAL, MAX_INTERVAL)
        log.info("Next spontaneous message in %.1f hours.", delay / 3600)
        await asyncio.sleep(delay)

        channels = self.bot.config.spontaneous_channels
        if not channels:
            return

        if self.bot.store.count == 0:
            return

        # Pick a random channel
        channel_id = random.choice(channels)
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            log.warning("Spontaneous channel %d not found.", channel_id)
            return

        try:
            async with channel.typing():  # type: ignore[union-attr]
                response = await self.bot.backend.generate(
                    prompt="",
                    examples=self.bot.store.get_all_text(),
                    recent_context=[],
                )
            if response:
                await channel.send(response)  # type: ignore[union-attr]
                log.info("Sent spontaneous message to #%s.", channel)  # type: ignore[union-attr]
        except Exception:
            log.exception("Failed to send spontaneous message")

    @spontaneous_loop.before_loop
    async def before_spontaneous(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: Faithy) -> None:
    await bot.add_cog(Scheduler(bot))
