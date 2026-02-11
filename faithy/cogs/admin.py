"""Admin cog — slash commands for managing example messages and backend."""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from faithy.bot import Faithy

log = logging.getLogger("faithy.admin")


def is_admin():
    """Decorator that restricts a command to the configured admin user."""

    async def predicate(interaction: discord.Interaction) -> bool:
        bot: Faithy = interaction.client  # type: ignore[assignment]
        if interaction.user.id != bot.config.admin_user_id:
            await interaction.response.send_message(
                "⛔ You are not authorised to use this command.", ephemeral=True
            )
            return False
        return True

    return app_commands.check(predicate)


def can_upload():
    """Decorator for commands that respect the ADMIN_ONLY_UPLOAD setting."""

    async def predicate(interaction: discord.Interaction) -> bool:
        bot: Faithy = interaction.client  # type: ignore[assignment]
        if bot.config.admin_only_upload:
            if interaction.user.id != bot.config.admin_user_id:
                await interaction.response.send_message(
                    "⛔ Only the administrator can perform this action.", ephemeral=True
                )
                return False
        return True

    return app_commands.check(predicate)


class Admin(commands.Cog):
    """Admin-only commands for managing the bot."""

    def __init__(self, bot: Faithy) -> None:
        self.bot = bot

    # ── /upload ──────────────────────────────────────────

    @app_commands.command(
        name="upload",
        description="Upload a .txt file of example messages.",
    )
    @app_commands.describe(file="A file with example messages")
    @can_upload()
    async def upload(
        self, interaction: discord.Interaction, file: discord.Attachment
    ) -> None:
        if not file.filename.endswith(".txt"):
            await interaction.response.send_message(
                "❌ Please upload a `.txt` file.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Sanitize filename (basic)
        filename = file.filename.replace("/", "_").replace("\\", "_")
        target_path = self.bot.config.data_dir / filename

        # Save to disk
        await file.save(target_path)
        
        # Reload store to pick up new file
        self.bot.store.reload()
        
        # Refresh backend with new messages
        await self.bot.refresh_backend()

        await interaction.followup.send(
            f"✅ Saved **{filename}** and reloaded. Total messages: {self.bot.store.count}.",
            ephemeral=True,
        )
        log.info("Admin uploaded file '%s'.", filename)

    # ── /add_message ─────────────────────────────────────

    @app_commands.command(
        name="add_message",
        description="Add a single example message.",
    )
    @app_commands.describe(text="The example message to add")
    @can_upload()
    async def add_message(
        self, interaction: discord.Interaction, text: str
    ) -> None:
        self.bot.store.add_messages([text])
        await self.bot.refresh_backend()
        await interaction.response.send_message(
            f"✅ Added message (total: {self.bot.store.count}).", ephemeral=True
        )

    # ── /list_messages ───────────────────────────────────

    @app_commands.command(
        name="list_messages",
        description="List stored example messages (paginated).",
    )
    @app_commands.describe(page="Page number (20 messages per page)")
    @is_admin()
    async def list_messages(
        self, interaction: discord.Interaction, page: int = 1
    ) -> None:
        msgs = self.bot.store.list_messages()
        if not msgs:
            await interaction.response.send_message(
                "📭 No messages stored.", ephemeral=True
            )
            return

        per_page = 20
        total_pages = (len(msgs) + per_page - 1) // per_page
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        chunk = msgs[start : start + per_page]

        lines = [f"`{start + i + 1}.` {m[:80]}" for i, m in enumerate(chunk)]
        header = f"**Messages** — page {page}/{total_pages} ({len(msgs)} total)\n"
        await interaction.response.send_message(
            header + "\n".join(lines), ephemeral=True
        )

    # ── /remove_message ──────────────────────────────────

    @app_commands.command(
        name="remove_message",
        description="Remove an example message by its index number.",
    )
    @app_commands.describe(index="1-based index of the message to remove")
    @can_upload()
    async def remove_message(
        self, interaction: discord.Interaction, index: int
    ) -> None:
        try:
            removed = self.bot.store.remove_message(index)
        except IndexError:
            await interaction.response.send_message(
                "❌ Invalid index.", ephemeral=True
            )
            return

        await self.bot.refresh_backend()
        await interaction.response.send_message(
            f"🗑️ Removed: _{removed[:80]}_\n(total: {self.bot.store.count})",
            ephemeral=True,
        )

    # ── /clear_messages ──────────────────────────────────

    @app_commands.command(
        name="clear_messages",
        description="Remove ALL example messages.",
    )
    @can_upload()
    async def clear_messages(self, interaction: discord.Interaction) -> None:
        count = self.bot.store.clear_messages()
        await self.bot.refresh_backend()
        await interaction.response.send_message(
            f"🗑️ Cleared **{count}** messages.", ephemeral=True
        )

    # ── /set_backend ─────────────────────────────────────

    @app_commands.command(
        name="set_backend",
        description="Switch the text-generation backend.",
    )
    @app_commands.describe(backend="Backend to use: markov, ollama, or openai")
    @app_commands.choices(
        backend=[
            app_commands.Choice(name="Markov chain (no API needed)", value="markov"),
            app_commands.Choice(name="Ollama (local LLM)", value="ollama"),
            app_commands.Choice(name="OpenAI-compatible (cloud)", value="openai"),
        ]
    )
    @is_admin()
    async def set_backend(
        self,
        interaction: discord.Interaction,
        backend: app_commands.Choice[str],
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            await self.bot.swap_backend(backend.value)
        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to switch backend: {e}", ephemeral=True
            )
            return
        await interaction.followup.send(
            f"✅ Backend switched to **{backend.name}**.", ephemeral=True
        )

    # ── /status ──────────────────────────────────────────

    @app_commands.command(
        name="status",
        description="Show current bot status and configuration.",
    )
    @is_admin()
    async def status(self, interaction: discord.Interaction) -> None:
        cfg = self.bot.config
        lines = [
            f"**Backend:** `{cfg.active_backend}`",
            f"**Messages:** {self.bot.store.count}",
            f"**Persona:** {cfg.persona_name}",
            f"**Reply probability:** {cfg.reply_probability:.1%}",
            f"**Debounce delay:** {cfg.debounce_delay}s",
            f"**Context limit:** {cfg.max_context_messages}",
            f"**Sample size:** {cfg.llm_sample_size}",
            f"**LLM Temp:** {cfg.llm_temperature}",
            f"**LLM Max Tokens:** {cfg.llm_max_tokens}",
            f"**Spontaneous channels:** {len(cfg.spontaneous_channels)}",
        ]
        await interaction.response.send_message(
            "\n".join(lines), ephemeral=True
        )

    # ── /generate_test ───────────────────────────────────

    @app_commands.command(
        name="generate_test",
        description="Trigger a test response based on a prompt.",
    )
    @app_commands.describe(prompt="The prompt to test against")
    @is_admin()
    async def generate_test(
        self, interaction: discord.Interaction, prompt: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            # Use balanced sampling for the test too
            sampled_examples = self.bot.store.get_sampled_messages(
                self.bot.config.llm_sample_size
            )
            examples_text = "\n".join(sampled_examples)

            response = await self.bot.backend.generate(
                prompt=prompt,
                examples=examples_text,
                recent_context=[],  # No context for manual test
            )
            if response:
                await interaction.followup.send(
                    f"**Prompt:** {prompt}\n**Response:** {response}",
                    ephemeral=True
                )
            else:
                await interaction.followup.send("⚠️ No response generated.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    # ── /download_messages ───────────────────────────────

    @app_commands.command(
        name="download_messages",
        description="Download all stored example messages as a .txt file.",
    )
    @is_admin()
    async def download_messages(self, interaction: discord.Interaction) -> None:
        text = self.bot.store.get_all_text()
        if not text:
            await interaction.response.send_message(
                "📭 No messages stored.", ephemeral=True
            )
            return

        buf = io.BytesIO(text.encode("utf-8"))
        file = discord.File(buf, filename="example_messages.txt")
        await interaction.response.send_message(
            file=file, ephemeral=True
        )


async def setup(bot: Faithy) -> None:
    await bot.add_cog(Admin(bot))
