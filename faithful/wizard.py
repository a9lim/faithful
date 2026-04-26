"""Interactive first-run wizard for faithful.

Pure stdin/stdout. Tested by monkeypatching ``builtins.input`` and
``getpass.getpass``. Nothing is written to disk until the very end.
"""
from __future__ import annotations

import getpass
from dataclasses import dataclass, field

BANNER = """
faithful first-run setup

This will walk you through configuring the bot. Takes ~2 minutes.
Press Ctrl+C any time to abort. Nothing is written to disk until
the end.
"""


@dataclass
class WizardState:
    """All values collected during a wizard run."""

    token: str = ""
    admin_ids: list[int] = field(default_factory=list)
    backend: str = ""
    api_key: str = ""
    model: str = ""
    base_url: str = ""


def print_banner() -> None:
    print(BANNER)


def prompt_token() -> str:
    """Prompt for a Discord bot token. Re-prompts on empty input."""
    print(
        "Discord bot token "
        "(https://discord.com/developers/applications -> your app -> Bot -> Reset Token):"
    )
    while True:
        raw = getpass.getpass("token (hidden): ")
        cleaned = raw.strip()
        if cleaned:
            return cleaned
        print("Empty token — please paste your bot token.")


def prompt_admin_ids() -> list[int]:
    """Prompt for Discord user IDs (comma-separated). Re-prompts on parse failure."""
    print(
        "\nYour Discord user ID(s), comma-separated. "
        "Enable Developer Mode in Discord -> right-click your name -> Copy User ID:"
    )
    while True:
        raw = input("admin IDs: ").strip()
        if not raw:
            print("Need at least one admin ID.")
            continue
        try:
            ids = [int(part.strip()) for part in raw.split(",") if part.strip()]
        except ValueError:
            print("Each ID must be an integer (e.g. 123456789012345678).")
            continue
        if ids:
            return ids
