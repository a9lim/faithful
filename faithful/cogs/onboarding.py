"""Welcome admins on first guild join + provide a /help slash command."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from faithful.bot import Faithful

log = logging.getLogger("faithful.onboarding")

_WELCOME_TEXT = (
    "Hey — I just joined **{guild}**.\n\n"
    "To teach me how you talk, run `/upload` with a `.txt` file of example "
    "messages, or `/add_message` to add them one at a time. Run `/help` any "
    "time to see all commands."
)


class Onboarding(commands.Cog):
    """Welcome message + /help command."""

    def __init__(self, bot: "Faithful") -> None:
        self.bot = bot
        self._seen_path: Path = self.bot.config.data_dir / "seen_guilds.json"

    def _load_seen(self) -> set[int]:
        if not self._seen_path.is_file():
            return set()
        try:
            return set(json.loads(self._seen_path.read_text()))
        except (OSError, ValueError):
            log.warning("Could not read %s; treating as empty.", self._seen_path)
            return set()

    def _save_seen(self, seen: set[int]) -> None:
        self._seen_path.parent.mkdir(parents=True, exist_ok=True)
        self._seen_path.write_text(json.dumps(sorted(seen)))

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        seen = self._load_seen()
        if guild.id in seen:
            return

        text = _WELCOME_TEXT.format(guild=guild.name)
        any_delivered = False

        for admin_id in self.bot.config.discord.admin_ids:
            user = self.bot.get_user(admin_id)
            if user is None:
                log.warning("Admin user %d not in cache; skipping.", admin_id)
                continue
            try:
                await user.send(text)
                any_delivered = True
            except discord.Forbidden:
                # DMs disabled — fall back to the first writable text channel.
                if await self._post_in_first_writable_channel(guild, admin_id, text):
                    any_delivered = True
            except discord.DiscordException as e:
                log.warning("Failed to DM admin %d: %s", admin_id, e)

        if not any_delivered:
            log.warning("Could not reach any admin in guild %d", guild.id)

        seen.add(guild.id)
        self._save_seen(seen)

    async def _post_in_first_writable_channel(
        self, guild: discord.Guild, admin_id: int, text: str
    ) -> bool:
        for chan in guild.text_channels:
            perms = chan.permissions_for(guild.me)
            if perms.send_messages:
                try:
                    await chan.send(f"<@{admin_id}>\n{text}")
                    return True
                except discord.DiscordException as e:
                    log.warning("Failed to post in %s: %s", chan, e)
        return False

    @app_commands.command(name="help", description="Show available commands.")
    async def help_cmd(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="faithful — commands",
            colour=discord.Colour.blurple(),
        )
        embed.add_field(
            name="Corpus (admin)",
            value=(
                "`/upload` — upload a .txt of example messages\n"
                "`/add_message` — add one message\n"
                "`/list_messages` — paginated list\n"
                "`/remove_message` — remove by index\n"
                "`/clear_messages` — wipe corpus\n"
                "`/download_messages` — export as .txt"
            ),
            inline=False,
        )
        embed.add_field(
            name="Memory",
            value=(
                "When `enable_memory` is on in the config, the bot manages "
                "per-channel memory automatically — no slash commands needed."
            ),
            inline=False,
        )
        embed.add_field(
            name="Diagnostics (admin)",
            value="`/status`, `/generate_test`",
            inline=False,
        )
        embed.set_footer(
            text="Config & data live at ~/.faithful/ on the host. "
                 "Run 'faithful info' on the host to see paths."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: "Faithful") -> None:
    await bot.add_cog(Onboarding(bot))
