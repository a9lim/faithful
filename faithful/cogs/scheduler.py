"""Scheduler cog — sends unprompted messages at random intervals."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import TYPE_CHECKING

from discord.ext import commands

from faithful.backends.base import GenerationRequest
from faithful.chunker import send_chunked
from faithful.prompt import format_system_prompt

if TYPE_CHECKING:
    from faithful.bot import Faithful

log = logging.getLogger("faithful.scheduler")


class Scheduler(commands.Cog):
    """Sends unprompted messages to configured channels."""

    def __init__(self, bot: Faithful) -> None:
        self.bot = bot
        self._task: asyncio.Task | None = None
        self._state_file = self.bot.config.data_dir / "scheduler_state.json"

    def _load_next_run(self) -> float | None:
        if not self._state_file.exists():
            return None
        try:
            with open(self._state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("next_run")
        except Exception:
            return None

    def _save_next_run(self, timestamp: float) -> None:
        try:
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump({"next_run": timestamp}, f)
        except Exception:
            log.warning("Failed to save scheduler state.")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())
            log.info("Spontaneous message scheduler started.")

    def cog_unload(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _loop(self) -> None:
        await self.bot.wait_until_ready()

        min_sec = self.bot.config.scheduler_min_hours * 3600
        max_sec = self.bot.config.scheduler_max_hours * 3600

        while True:
            try:
                next_run = self._load_next_run()
                now = time.time()

                if next_run and next_run > now:
                    delay = next_run - now
                    log.info("Next spontaneous message in %.1f hours.", delay / 3600)
                else:
                    delay = random.uniform(min_sec, max_sec)
                    self._save_next_run(now + delay)
                    log.info(
                        "Scheduled spontaneous message in %.1f hours.", delay / 3600
                    )

                await asyncio.sleep(delay)
                self._save_next_run(0)

                await self._send_spontaneous()

            except asyncio.CancelledError:
                return
            except Exception:
                log.exception("Scheduler error — retrying in 1 hour.")
                await asyncio.sleep(3600)

    async def _send_spontaneous(self) -> None:
        channels = self.bot.config.spontaneous_channels
        if not channels:
            return

        if self.bot.store.count == 0:
            return

        channel_id = random.choice(channels)
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            log.warning("Spontaneous channel %d not found.", channel_id)
            return

        cfg = self.bot.config
        sampled = self.bot.store.get_sampled_messages(cfg.sample_size)
        system_prompt = format_system_prompt(
            cfg.system_prompt, cfg.persona_name, sampled
        )

        request = GenerationRequest(
            prompt="",
            system_prompt=system_prompt,
        )

        try:
            response = await self.bot.backend.generate(request)
            if response:
                await send_chunked(channel, response)  # type: ignore[arg-type]
                log.info("Sent spontaneous message to #%s.", channel)
        except Exception:
            log.exception("Failed to send spontaneous message")


async def setup(bot: Faithful) -> None:
    await bot.add_cog(Scheduler(bot))
