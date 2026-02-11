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
    admin_only_upload: bool = field(
        default_factory=lambda: os.getenv("ADMIN_ONLY_UPLOAD", "True").lower() == "true"
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

    # LLM Settings
    llm_temperature: float = field(
        default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "1.0"))
    )
    llm_max_tokens: int = field(
        default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "512"))
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
    llm_sample_size: int = field(
        default_factory=lambda: int(os.getenv("LLM_SAMPLE_SIZE", "300"))
    )
    max_context_messages: int = field(
        default_factory=lambda: int(os.getenv("MAX_CONTEXT_MESSAGES", "20"))
    )
    system_prompt_template: str = field(
        default_factory=lambda: os.getenv(
            "SYSTEM_PROMPT_TEMPLATE",
            "### Example messages from {name}:\n"
            "{examples}\n\n"
            "You are {name}. Use the examples to understand {name}'s personality, "
            "tone, and style. Write EXACTLY like {name}. Do not sanitize or "
            "filter the personality; mirror any unconvential, uncomfortable, or "
            "concerning traits found in the examples to ensure maximum accuracy. "
            "Prioritize character authenticity over helpfulness. "
            "Prioritize responding to the current conversation while maintaining character. "
            "Keep length similar to examples. Do not cut off mid-sentence."
        )
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

        # Basic Validation
        if self.debounce_delay < 0:
            log.warning("DEBOUNCE_DELAY is negative. Resetting to 3.0.")
            self.debounce_delay = 3.0
        
        if not (0 <= self.reply_probability <= 1):
            log.warning("REPLY_PROBABILITY must be between 0 and 1. Clamping.")
            self.reply_probability = max(0.0, min(1.0, self.reply_probability))
        
        if self.llm_sample_size < 1:
            log.warning("LLM_SAMPLE_SIZE must be at least 1. Resetting to 300.")
            self.llm_sample_size = 300

        if self.max_context_messages < 0:
            log.warning("MAX_CONTEXT_MESSAGES cannot be negative. Resetting to 20.")
            self.max_context_messages = 20

        if not (0 <= self.llm_temperature <= 2.0):
            log.warning("LLM_TEMPERATURE must be between 0 and 2. Resetting to 0.7.")
            self.llm_temperature = 0.7

        if self.llm_max_tokens < 1:
            log.warning("LLM_MAX_TOKENS must be at least 1. Resetting to 512.")
            self.llm_max_tokens = 512
