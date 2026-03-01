from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from .backends import get_backend
from .store import MessageStore

if TYPE_CHECKING:
    from .backends.base import Backend
    from .config import Config
    from .memory import MemoryStore as MemoryStoreType

log = logging.getLogger("faithful")


class Faithful(commands.Bot):
    """The persona-emulating Discord bot."""

    config: Config
    store: MessageStore
    backend: Backend
    memory_store: MemoryStoreType | None

    def __init__(self, config: Config) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            status=discord.Status.online,
            activity=discord.Game(name="being myself"),
        )

        self.config = config
        self.store = MessageStore(config)
        self.backend = get_backend(config.active_backend, config)
        self.memory_store = None

        if config.enable_memory:
            from .memory import MemoryStore
            self.memory_store = MemoryStore(config.data_dir)

        self.backend.memory_store = self.memory_store

    async def setup_hook(self) -> None:
        await self.load_extension("faithful.cogs.admin")
        await self.load_extension("faithful.cogs.chat")
        await self.load_extension("faithful.cogs.scheduler")

        examples = self.store.list_messages()
        if examples:
            await self.backend.setup(examples)
            log.info(
                "Backend '%s' initialised with %d examples.",
                self.config.active_backend,
                self.store.count,
            )
        else:
            log.warning("No example messages found. Use /upload to add some.")

    async def on_ready(self) -> None:
        log.info("Logged in as %s (ID: %s)", self.user, self.user.id)
        activity = discord.CustomActivity(name="being me")
        await self.change_presence(activity=activity)

    async def refresh_backend(self) -> None:
        """Re-setup the current backend (call after message corpus changes)."""
        examples = self.store.list_messages()
        await self.backend.setup(examples)
