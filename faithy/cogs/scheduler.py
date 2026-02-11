"""Scheduler cog — sends 1–2 unprompted messages per day at random times."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
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
        self._state_file = self.bot.config.data_dir / "scheduler_state.json"

    def _load_next_run(self) -> float | None:
        """Load the next scheduled run time from disk."""
        if not self._state_file.exists():
            return None
        try:
            with open(self._state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("next_run")
        except Exception:
            return None

    def _save_next_run(self, timestamp: float) -> None:
        """Save the next scheduled run time to disk."""
        try:
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump({"next_run": timestamp}, f)
        except Exception:
            log.warning("Failed to save scheduler state.")

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
        # 1. Determine wait time
        next_run = self._load_next_run()
        now = time.time()

        if next_run and next_run > now:
            delay = next_run - now
            log.info("Resuming scheduler: next spontaneous message in %.1f hours.", delay / 3600)
        else:
            delay = random.uniform(MIN_INTERVAL, MAX_INTERVAL)
            self._save_next_run(now + delay)
            log.info("Next spontaneous message scheduled in %.1f hours.", delay / 3600)

        # 2. Wait
        await asyncio.sleep(delay)

        # 3. Reset state for next iteration (so we generate a new one next time)
        self._save_next_run(0)

        # 4. Attempt to send
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
            # Spontaneous messages use an empty prompt to trigger personality-based text
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
