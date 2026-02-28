from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv, set_key

log = logging.getLogger("faithful.config")

# Load .env from the project root (two levels up from this file)
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)

DEFAULT_SYSTEM_PROMPT = (
    "You are {name}. Use the following examples to understand {name}'s personality, "
    "tone, and style. Write EXACTLY like {name}. Do not sanitize or "
    "filter the personality; mirror any unconvential, uncomfortable, or "
    "concerning traits found in the examples to ensure maximum accuracy. "
    "Be as authentic as possible to the provided messages. "
    "Respond to the current conversation while maintaining a consistent personality. "
    "Do not cut off mid-sentence. You must finish your sentences! "
    "Use newlines to create line breaks between messages.\n"
    "Example messages from {name}:\n"
    "{examples}\n"
    "You are {name}. Use the previous examples to understand {name}'s personality, "
    "tone, and style. Write EXACTLY like {name}. Do not sanitize or "
    "filter the personality; mirror any unconvential, uncomfortable, or "
    "concerning traits found in the examples to ensure maximum accuracy. "
    "Be as authentic as possible to the provided messages. "
    "Prioritize responding to the current conversation while maintaining a consistent personality. "
    "Do not cut off mid-sentence. You must finish your sentences! "
    "Use newlines to create line breaks between messages."
)

# Maps .env key names to Config field names for update_env()
_ENV_TO_FIELD: dict[str, str] = {
    "ACTIVE_BACKEND": "active_backend",
    "OLLAMA_MODEL": "ollama_model",
    "OLLAMA_HOST": "ollama_host",
    "OPENAI_API_KEY": "openai_api_key",
    "OPENAI_MODEL": "openai_model",
    "OPENAI_BASE_URL": "openai_base_url",
    "GEMINI_API_KEY": "gemini_api_key",
    "GEMINI_MODEL": "gemini_model",
    "ANTHROPIC_API_KEY": "anthropic_api_key",
    "ANTHROPIC_MODEL": "anthropic_model",
    "LLM_TEMPERATURE": "llm_temperature",
    "LLM_MAX_TOKENS": "llm_max_tokens",
    "REPLY_PROBABILITY": "reply_probability",
    "PERSONA_NAME": "persona_name",
    "DEBOUNCE_DELAY": "debounce_delay",
    "CONVERSATION_EXPIRY": "conversation_expiry",
    "LLM_SAMPLE_SIZE": "llm_sample_size",
    "MAX_CONTEXT_MESSAGES": "max_context_messages",
}


def _clamp(value: float, lo: float, hi: float, name: str, default: float) -> float:
    """Clamp *value* to [lo, hi], warning and returning *default* if out of range."""
    if lo <= value <= hi:
        return value
    log.warning("%s=%.4g out of range [%.4g, %.4g]. Resetting to %.4g.", name, value, lo, hi, default)
    return default


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

    # Gemini
    gemini_api_key: str = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "")
    )
    gemini_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    )

    # Anthropic
    anthropic_api_key: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "")
    )
    anthropic_model: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    )

    # LLM Settings
    llm_temperature: float = field(
        default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "1.0"))
    )
    llm_max_tokens: int = field(
        default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "1024"))
    )

    # Behaviour
    spontaneous_channels: list[int] = field(default_factory=list)
    reply_probability: float = field(
        default_factory=lambda: float(os.getenv("REPLY_PROBABILITY", "0.02"))
    )
    persona_name: str = field(
        default_factory=lambda: os.getenv("PERSONA_NAME", "faithful")
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
        default_factory=lambda: os.getenv("SYSTEM_PROMPT_TEMPLATE", DEFAULT_SYSTEM_PROMPT)
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

        # Validation
        self.debounce_delay = _clamp(self.debounce_delay, 0, 60, "DEBOUNCE_DELAY", 3.0)
        self.reply_probability = _clamp(self.reply_probability, 0, 1, "REPLY_PROBABILITY", 0.02)
        self.llm_temperature = _clamp(self.llm_temperature, 0, 2, "LLM_TEMPERATURE", 1.0)

        if self.llm_sample_size < 1:
            log.warning("LLM_SAMPLE_SIZE must be at least 1. Resetting to 300.")
            self.llm_sample_size = 300

        if self.max_context_messages < 0:
            log.warning("MAX_CONTEXT_MESSAGES cannot be negative. Resetting to 20.")
            self.max_context_messages = 20

        if self.llm_max_tokens < 1:
            log.warning("LLM_MAX_TOKENS must be at least 1. Resetting to 1024.")
            self.llm_max_tokens = 1024

    def update_env(self, key: str, value: str) -> None:
        """Update a key in the .env file and set the corresponding in-memory field."""
        set_key(str(_ENV_PATH), key, str(value))

        field_name = _ENV_TO_FIELD.get(key)
        if field_name is None:
            return

        current = getattr(self, field_name, None)
        if current is None:
            return

        # Cast to the same type as the existing field
        if isinstance(current, float):
            setattr(self, field_name, float(value))
        elif isinstance(current, int):
            setattr(self, field_name, int(value))
        else:
            setattr(self, field_name, value)
