"""Configuration loader — reads .env and exposes a Config dataclass."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (two levels up from this file)
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)


@dataclass
class Config:
    """Bot-wide configuration sourced from environment variables."""

    # Discord
    discord_token: str = field(default_factory=lambda: os.environ["DISCORD_TOKEN"])
    admin_user_id: int = field(
        default_factory=lambda: int(os.environ["ADMIN_USER_ID"])
    )

    # Active backend
    active_backend: str = field(
        default_factory=lambda: os.getenv("ACTIVE_BACKEND", "markov")
    )

    # Ollama
    ollama_model: str = field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3")
    )
    ollama_host: str = field(
        default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434")
    )

    # OpenAI-compatible
    openai_api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "")
    )
    openai_model: str = field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    )
    openai_base_url: str = field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )

    # Behaviour
    spontaneous_channels: list[int] = field(default_factory=list)
    reply_probability: float = field(
        default_factory=lambda: float(os.getenv("REPLY_PROBABILITY", "0.02"))
    )
    persona_name: str = field(
        default_factory=lambda: os.getenv("PERSONA_NAME", "faithy")
    )
    debounce_delay: float = field(
        default_factory=lambda: float(os.getenv("DEBOUNCE_DELAY", "3.0"))
    )
    conversation_expiry: float = field(
        default_factory=lambda: float(os.getenv("CONVERSATION_EXPIRY", "300.0"))
    )

    # Data directory
    data_dir: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "data"
    )

    def __post_init__(self) -> None:
        # Parse spontaneous channels from comma-separated env var
        raw = os.getenv("SPONTANEOUS_CHANNELS", "")
        if raw.strip():
            self.spontaneous_channels = [
                int(ch.strip()) for ch in raw.split(",") if ch.strip()
            ]

        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
