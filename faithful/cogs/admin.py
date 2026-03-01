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
        if interaction.user.id not in bot.config.admin_ids:
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
            f"**Backend:** `{cfg.active_backend}`",
            f"**Model:** `{cfg.model or '(default)'}`",
            f"**Messages:** {self.bot.store.count}",
            f"**Persona:** {cfg.persona_name}",
            f"**Reply probability:** {cfg.reply_probability:.1%}",
            f"**Reaction probability:** {cfg.reaction_probability:.1%}",
            f"**Debounce delay:** {cfg.debounce_delay}s",
            f"**Context limit:** {cfg.max_context_messages}",
            f"**Sample size:** {cfg.sample_size}",
            f"**Temperature:** {cfg.temperature}",
            f"**Max tokens:** {cfg.max_tokens}",
            f"**Spontaneous channels:** {len(cfg.spontaneous_channels)}",
            f"**Web search:** {'on' if cfg.enable_web_search else 'off'}",
            f"**Memory:** {'on' if cfg.enable_memory else 'off'}",
            f"**Admins:** {len(cfg.admin_ids)}",
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
            sampled = self.bot.store.get_sampled_messages(self.bot.config.sample_size)
            system_prompt = format_system_prompt(
                self.bot.config.system_prompt,
                self.bot.config.persona_name,
                sampled,
                custom_emojis="",
            )
            request = GenerationRequest(
                prompt=prompt,
                system_prompt=system_prompt,
            )
            response = await self.bot.backend.generate(request)
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
    if interaction.user.id not in bot.config.admin_ids:
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


class Memory(
    app_commands.Group, name="memory", description="Manage bot memories."
):
    """Admin commands for managing per-user and per-channel memories."""

    def __init__(self, bot: Faithful) -> None:
        super().__init__()
        self.bot = bot

    @app_commands.command(name="list", description="List memories for a user or channel.")
    @app_commands.describe(
        target="Whether to list user or channel memories",
        user="The user to list memories for (user target only)",
    )
    @app_commands.choices(
        target=[
            app_commands.Choice(name="user", value="user"),
            app_commands.Choice(name="channel", value="channel"),
        ]
    )
    @is_admin()
    async def memory_list(
        self,
        interaction: discord.Interaction,
        target: app_commands.Choice[str],
        user: discord.User | None = None,
    ) -> None:
        store = self.bot.memory_store
        if store is None:
            await interaction.response.send_message(
                "\u274c Memory is not enabled.", ephemeral=True
            )
            return

        if target.value == "user":
            if user is None:
                await interaction.response.send_message(
                    "\u274c Please specify a user.", ephemeral=True
                )
                return
            name, facts = store.get_user_memories(user.id)
            if not facts:
                await interaction.response.send_message(
                    f"\U0001f4ed No memories for **{user.display_name}**.", ephemeral=True
                )
                return
            lines = [f"`{i + 1}.` {f}" for i, f in enumerate(facts)]
            header = f"**Memories for {user.display_name}** ({len(facts)} total)\n"
            await interaction.response.send_message(header + "\n".join(lines), ephemeral=True)
        else:
            channel_id = interaction.channel_id
            memories = store.get_channel_memories(channel_id)
            if not memories:
                await interaction.response.send_message(
                    "\U0001f4ed No memories for this channel.", ephemeral=True
                )
                return
            lines = [f"`{i + 1}.` {m}" for i, m in enumerate(memories)]
            header = f"**Channel memories** ({len(memories)} total)\n"
            await interaction.response.send_message(header + "\n".join(lines), ephemeral=True)

    @app_commands.command(name="add", description="Add a memory for a user or channel.")
    @app_commands.describe(
        target="Whether to add to user or channel memories",
        text="The memory to add",
        user="The user to add a memory for (user target only)",
    )
    @app_commands.choices(
        target=[
            app_commands.Choice(name="user", value="user"),
            app_commands.Choice(name="channel", value="channel"),
        ]
    )
    @is_admin()
    async def memory_add(
        self,
        interaction: discord.Interaction,
        target: app_commands.Choice[str],
        text: str,
        user: discord.User | None = None,
    ) -> None:
        store = self.bot.memory_store
        if store is None:
            await interaction.response.send_message(
                "\u274c Memory is not enabled.", ephemeral=True
            )
            return

        if target.value == "user":
            if user is None:
                await interaction.response.send_message(
                    "\u274c Please specify a user.", ephemeral=True
                )
                return
            store.add_user_memory(user.id, user.display_name, text)
            await interaction.response.send_message(
                f"\u2705 Added memory for **{user.display_name}**.", ephemeral=True
            )
        else:
            store.add_channel_memory(interaction.channel_id, text)
            await interaction.response.send_message(
                "\u2705 Added channel memory.", ephemeral=True
            )

    @app_commands.command(name="remove", description="Remove a memory by index.")
    @app_commands.describe(
        target="Whether to remove from user or channel memories",
        index="1-based index of the memory to remove",
        user="The user to remove a memory from (user target only)",
    )
    @app_commands.choices(
        target=[
            app_commands.Choice(name="user", value="user"),
            app_commands.Choice(name="channel", value="channel"),
        ]
    )
    @is_admin()
    async def memory_remove(
        self,
        interaction: discord.Interaction,
        target: app_commands.Choice[str],
        index: int,
        user: discord.User | None = None,
    ) -> None:
        store = self.bot.memory_store
        if store is None:
            await interaction.response.send_message(
                "\u274c Memory is not enabled.", ephemeral=True
            )
            return

        try:
            if target.value == "user":
                if user is None:
                    await interaction.response.send_message(
                        "\u274c Please specify a user.", ephemeral=True
                    )
                    return
                removed = store.remove_user_memory(user.id, index - 1)
                await interaction.response.send_message(
                    f"\U0001f5d1\ufe0f Removed memory for **{user.display_name}**: _{removed[:80]}_",
                    ephemeral=True,
                )
            else:
                removed = store.remove_channel_memory(interaction.channel_id, index - 1)
                await interaction.response.send_message(
                    f"\U0001f5d1\ufe0f Removed channel memory: _{removed[:80]}_",
                    ephemeral=True,
                )
        except IndexError:
            await interaction.response.send_message(
                "\u274c Invalid index.", ephemeral=True
            )

    @app_commands.command(name="clear", description="Clear all memories for a user or channel.")
    @app_commands.describe(
        target="Whether to clear user or channel memories",
        user="The user to clear memories for (user target only)",
    )
    @app_commands.choices(
        target=[
            app_commands.Choice(name="user", value="user"),
            app_commands.Choice(name="channel", value="channel"),
        ]
    )
    @is_admin()
    async def memory_clear(
        self,
        interaction: discord.Interaction,
        target: app_commands.Choice[str],
        user: discord.User | None = None,
    ) -> None:
        store = self.bot.memory_store
        if store is None:
            await interaction.response.send_message(
                "\u274c Memory is not enabled.", ephemeral=True
            )
            return

        if target.value == "user":
            if user is None:
                await interaction.response.send_message(
                    "\u274c Please specify a user.", ephemeral=True
                )
                return
            count = store.clear_user_memories(user.id)
            await interaction.response.send_message(
                f"\U0001f5d1\ufe0f Cleared **{count}** memories for **{user.display_name}**.",
                ephemeral=True,
            )
        else:
            count = store.clear_channel_memories(interaction.channel_id)
            await interaction.response.send_message(
                f"\U0001f5d1\ufe0f Cleared **{count}** channel memories.",
                ephemeral=True,
            )


async def setup(bot: Faithful) -> None:
    await bot.add_cog(Admin(bot))
    bot.tree.add_command(Memory(bot))
    bot.tree.add_command(add_to_persona)
