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
        if not ids:
            print("Need at least one valid ID.")
            continue
        return ids


BACKEND_DEFAULTS: dict[str, dict[str, str]] = {
    "openai": {
        "label": "OpenAI (GPT models)",
        "key_url": "https://platform.openai.com/api-keys",
        "default_model": "gpt-4o-mini",
    },
    "openai-compatible": {
        "label": "Ollama / LM Studio / vLLM / any OpenAI-compatible server",
        "key_url": "",
        "default_model": "",
    },
    "gemini": {
        "label": "Google Gemini",
        "key_url": "https://aistudio.google.com/apikey",
        "default_model": "gemini-2.0-flash",
    },
    "anthropic": {
        "label": "Anthropic Claude",
        "key_url": "https://console.anthropic.com/settings/keys",
        "default_model": "claude-haiku-4-5",
    },
}

# Stable order matches the menu the user sees.
_BACKEND_ORDER = ["openai", "openai-compatible", "gemini", "anthropic"]


def prompt_backend() -> str:
    """Show the numbered backend menu and return the chosen key."""
    print("\nChoose a backend:")
    for i, name in enumerate(_BACKEND_ORDER, start=1):
        print(f"  {i}) {name:<20} — {BACKEND_DEFAULTS[name]['label']}")
    while True:
        raw = input("backend [1-4]: ").strip()
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(_BACKEND_ORDER):
                return _BACKEND_ORDER[idx - 1]
        print("Pick a number 1-4.")


def prompt_credentials(backend: str) -> tuple[str, str, str]:
    """Prompt for api_key, model, base_url. Returns (api_key, model, base_url)."""
    info = BACKEND_DEFAULTS[backend]

    if backend == "openai-compatible":
        print(
            "\nbase_url for your OpenAI-compatible server "
            "(e.g. http://localhost:11434/v1 for Ollama):"
        )
        while True:
            base_url = input("base_url: ").strip()
            if base_url:
                break
            print("base_url is required for openai-compatible.")
        print(
            "API key (press Enter to skip if your local server doesn't need one):"
        )
        api_key = getpass.getpass("api_key (hidden): ").strip()
    else:
        base_url = ""
        if info["key_url"]:
            print(f"\nGet your API key at {info['key_url']}")
        api_key = getpass.getpass("api_key (hidden): ").strip()

    default_model = info["default_model"]
    if default_model:
        prompt = f"model name [{default_model}]: "
    else:
        prompt = "model name: "
    while True:
        raw = input(prompt).strip()
        if raw:
            return api_key, raw, base_url
        if default_model:
            return api_key, default_model, base_url
        print("Model name is required for this backend.")
