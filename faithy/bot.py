"""Main Discord bot class."""

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

log = logging.getLogger("faithy")


class Faithy(commands.Bot):
    """The persona-emulating Discord bot."""

    config: Config
    store: MessageStore
    backend: Backend

    def __init__(self, config: Config) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix="!",  # unused — we use slash commands
            intents=intents,
            status=discord.Status.online,
            activity=discord.Game(name="being myself"),
        )

        self.config = config
        self.store = MessageStore(config)
        self.backend = get_backend(config.active_backend, config)

    async def setup_hook(self) -> None:
        """Load cogs and sync commands."""
        await self.load_extension("faithy.cogs.admin")
        await self.load_extension("faithy.cogs.chat")
        await self.load_extension("faithy.cogs.scheduler")

        # Build initial backend model from stored examples
        examples = self.store.list_messages()
        if examples:
            await self.backend.setup(examples)
            log.info("Backend '%s' initialised with %d examples.",
                     self.config.active_backend, self.store.count)
        else:
            log.warning("No example messages found. Use /upload to add some.")

    async def on_ready(self) -> None:
        log.info("Logged in as %s (ID: %s)", self.user, self.user.id)
        
        # Update presence
        activity = discord.CustomActivity(name=f"being me")
        await self.change_presence(activity=activity)
        
        # Sync slash commands globally
        synced = await self.tree.sync()
        log.info("Synced %d slash commands.", len(synced))

    async def swap_backend(self, name: str) -> None:
        """Hot-swap the active text-generation backend."""
        self.backend = get_backend(name, self.config)
        self.config.active_backend = name
        examples = self.store.list_messages()
        if examples:
            await self.backend.setup(examples)
        log.info("Swapped backend to '%s'.", name)

    async def refresh_backend(self) -> None:
        """Re-setup the current backend (call after message corpus changes)."""
        examples = self.store.list_messages()
        await self.backend.setup(examples)
