from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from faithful.backends.base import GenerationRequest
from faithful.prompt import format_system_prompt

if TYPE_CHECKING:
    from faithful.bot import Faithful

log = logging.getLogger("faithful.admin")


def is_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        bot: Faithful = interaction.client  # type: ignore[assignment]
        if interaction.user.id not in bot.config.discord.admin_ids:
            await interaction.response.send_message(
                "\u26d4 You are not authorised to use this command.", ephemeral=True
            )
            return False
        return True

    return app_commands.check(predicate)


class Admin(commands.Cog):
    """Admin-only commands for managing the bot."""

    def __init__(self, bot: Faithful) -> None:
        self.bot = bot

    # ── Messages ─────────────────────────────────────────

    @app_commands.command(
        name="upload",
        description="Upload a .txt file of example messages.",
    )
    @app_commands.describe(file="A file with example messages")
    @is_admin()
    async def upload(
        self, interaction: discord.Interaction, file: discord.Attachment
    ) -> None:
        if not file.filename.endswith(".txt"):
            await interaction.response.send_message(
                "\u274c Please upload a `.txt` file.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        filename = file.filename.replace("/", "_").replace("\\", "_")
        target_path = self.bot.config.data_dir / filename

        await file.save(target_path)
        self.bot.store.reload()
        await self.bot.refresh_backend()

        await interaction.followup.send(
            f"\u2705 Saved **{filename}** and reloaded. "
            f"Total messages: {self.bot.store.count}.",
            ephemeral=True,
        )
        log.info("Admin uploaded file '%s'.", filename)

    @app_commands.command(
        name="add_message",
        description="Add a single example message.",
    )
    @app_commands.describe(text="The example message to add")
    @is_admin()
    async def add_message(
        self, interaction: discord.Interaction, text: str
    ) -> None:
        self.bot.store.add_messages([text])
        await self.bot.refresh_backend()
        await interaction.response.send_message(
            f"\u2705 Added message (total: {self.bot.store.count}).", ephemeral=True
        )

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
                "\U0001f4ed No messages stored.", ephemeral=True
            )
            return

        per_page = 20
        total_pages = (len(msgs) + per_page - 1) // per_page
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        chunk = msgs[start : start + per_page]

        lines = [f"`{start + i + 1}.` {m[:80]}" for i, m in enumerate(chunk)]
        header = f"**Messages** \u2014 page {page}/{total_pages} ({len(msgs)} total)\n"
        await interaction.response.send_message(
            header + "\n".join(lines), ephemeral=True
        )

    @app_commands.command(
        name="remove_message",
        description="Remove an example message by its index number.",
    )
    @app_commands.describe(index="1-based index of the message to remove")
    @is_admin()
    async def remove_message(
        self, interaction: discord.Interaction, index: int
    ) -> None:
        try:
            removed = self.bot.store.remove_message(index)
        except IndexError:
            await interaction.response.send_message(
                "\u274c Invalid index.", ephemeral=True
            )
            return

        await self.bot.refresh_backend()
        await interaction.response.send_message(
            f"\U0001f5d1\ufe0f Removed: _{removed[:80]}_\n"
            f"(total: {self.bot.store.count})",
            ephemeral=True,
        )

    @app_commands.command(
        name="clear_messages",
        description="Remove ALL example messages.",
    )
    @is_admin()
    async def clear_messages(self, interaction: discord.Interaction) -> None:
        count = self.bot.store.clear_messages()
        await self.bot.refresh_backend()
        await interaction.response.send_message(
            f"\U0001f5d1\ufe0f Cleared **{count}** messages.", ephemeral=True
        )

    @app_commands.command(
        name="download_messages",
        description="Download all stored example messages as a .txt file.",
    )
    @is_admin()
    async def download_messages(self, interaction: discord.Interaction) -> None:
        text = self.bot.store.get_all_text()
        if not text:
            await interaction.response.send_message(
                "\U0001f4ed No messages stored.", ephemeral=True
            )
            return

        buf = io.BytesIO(text.encode("utf-8"))
        file = discord.File(buf, filename="example_messages.txt")
        await interaction.response.send_message(file=file, ephemeral=True)

    # ── Status & Testing ────────────────────────────────

    @app_commands.command(
        name="status",
        description="Show current bot status and configuration.",
    )
    @is_admin()
    async def status(self, interaction: discord.Interaction) -> None:
        cfg = self.bot.config
        lines = [
            f"**Backend:** `{cfg.backend.active}`",
            f"**Model:** `{cfg.backend.model or '(default)'}`",
            f"**Messages:** {self.bot.store.count}",
            f"**Persona:** {cfg.behavior.persona_name}",
            f"**Reply probability:** {cfg.behavior.reply_probability:.1%}",
            f"**Reaction probability:** {cfg.behavior.reaction_probability:.1%}",
            f"**Debounce delay:** {cfg.behavior.debounce_delay}s",
            f"**Context limit:** {cfg.behavior.max_context_messages}",
            f"**Sample size:** {cfg.llm.sample_size}",
            f"**Temperature:** {cfg.llm.temperature}",
            f"**Max tokens:** {cfg.llm.max_tokens}",
            f"**Spontaneous channels:** {len(cfg.scheduler.channels)}",
            f"**Web search:** {'on' if cfg.behavior.enable_web_search else 'off'}",
            f"**Memory:** {'on' if cfg.behavior.enable_memory else 'off'}",
            f"**Admins:** {len(cfg.discord.admin_ids)}",
        ]
        await interaction.response.send_message(
            "\n".join(lines), ephemeral=True
        )

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
            sampled = self.bot.store.get_sampled_messages(self.bot.config.llm.sample_size)
            system_prompt = format_system_prompt(
                self.bot.config.behavior.system_prompt,
                self.bot.config.behavior.persona_name,
                sampled,
                custom_emojis="",
            )
            request = GenerationRequest(
                prompt=prompt,
                system_prompt=system_prompt,
            )
            parts = [r async for r in self.bot.backend.generate(request)]
            response = "\n\n".join(parts)
            if response:
                await interaction.followup.send(
                    f"**Prompt:** {prompt}\n**Response:** {response}",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "\u26a0\ufe0f No response generated.", ephemeral=True
                )
        except Exception as e:
            await interaction.followup.send(f"\u274c Error: {e}", ephemeral=True)


@app_commands.context_menu(name="Add to Persona")
async def add_to_persona(
    interaction: discord.Interaction, message: discord.Message
) -> None:
    bot: Faithful = interaction.client  # type: ignore[assignment]
    if interaction.user.id not in bot.config.discord.admin_ids:
        await interaction.response.send_message(
            "\u26d4 Only administrators can perform this action.", ephemeral=True
        )
        return

    if not message.content.strip():
        await interaction.response.send_message(
            "\u274c This message has no text.", ephemeral=True
        )
        return

    bot.store.add_messages([message.content])
    await bot.refresh_backend()
    await interaction.response.send_message(
        f"\u2705 Added message to persona (total: {bot.store.count}).",
        ephemeral=True,
    )


async def setup(bot: Faithful) -> None:
    await bot.add_cog(Admin(bot))
    bot.tree.add_command(add_to_persona)
