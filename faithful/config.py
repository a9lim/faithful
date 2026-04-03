from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

log = logging.getLogger("faithful.config")

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.toml"

DEFAULT_SYSTEM_PROMPT = (
    "You are {name}. Here's how {name} talks:\n\n"
    "{examples}\n"
    "Write exactly like {name} -- same slang, same punctuation, same energy.\n"
    "If {name} types in all lowercase, you do too. If {name} is blunt, be blunt.\n"
    "Don't clean up the language, don't add politeness, don't over-explain.\n\n"
    "Keep your messages short and natural like a real Discord user.\n"
    "Use newlines to break up separate thoughts.\n\n"
    "You can react to messages by including [react: emoji] at the end of your response.\n"
    "Use standard emoji or any of the server's custom emoji.\n"
    "{custom_emojis}"
)


def _load_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def _clamp(value: float, lo: float, hi: float, name: str, default: float) -> float:
    if lo <= value <= hi:
        return value
    log.warning("%s=%.4g out of range [%.4g, %.4g]; using %.4g.", name, value, lo, hi, default)
    return default


def _parse_admin_ids(env_val: str | None, toml_val: Any) -> list[int]:
    if env_val:
        return [int(x.strip()) for x in env_val.split(",") if x.strip()]
    if isinstance(toml_val, list):
        return [int(x) for x in toml_val]
    if isinstance(toml_val, int) and toml_val:
        return [toml_val]
    return []


def _merge_dataclass(instance: Any, overrides: dict) -> None:
    """Recursively merge a dict of overrides into a dataclass instance."""
    for key, value in overrides.items():
        if not hasattr(instance, key):
            continue
        current = getattr(instance, key)
        if isinstance(value, dict) and hasattr(current, "__dataclass_fields__"):
            _merge_dataclass(current, value)
        else:
            setattr(instance, key, value)


# ── Nested config sections ──────────────────────────────


@dataclass
class DiscordConfig:
    token: str = ""
    admin_ids: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.token:
            token = os.environ.get("DISCORD_TOKEN", "")
            if token:
                self.token = token
        admin_env = os.environ.get("ADMIN_USER_IDS") or os.environ.get("ADMIN_USER_ID")
        if admin_env:
            self.admin_ids = _parse_admin_ids(admin_env, None)


@dataclass
class BackendConfig:
    active: str = "openai-compatible"
    api_key: str = ""
    model: str = ""
    base_url: str = ""
    enable_thinking: bool = True
    enable_compaction: bool = True
    enable_1m_context: bool = True

    def __post_init__(self) -> None:
        api_env = os.environ.get("API_KEY", "")
        if api_env:
            self.api_key = api_env


@dataclass
class LLMConfig:
    temperature: float = 1.0
    max_tokens: int = 16000
    sample_size: int = 300

    def __post_init__(self) -> None:
        self.temperature = _clamp(self.temperature, 0, 2, "temperature", 1.0)
        self.sample_size = max(1, self.sample_size)
        self.max_tokens = max(1, self.max_tokens)


@dataclass
class BehaviorConfig:
    persona_name: str = "faithful"
    reply_probability: float = 0.02
    reaction_probability: float = 0.05
    debounce_delay: float = 3.0
    conversation_expiry: float = 300.0
    max_context_messages: int = 20
    enable_web_search: bool = False
    enable_memory: bool = False
    max_session_messages: int = 50
    system_prompt: str = ""

    def __post_init__(self) -> None:
        self.debounce_delay = _clamp(self.debounce_delay, 0, 60, "debounce_delay", 3.0)
        self.reply_probability = _clamp(self.reply_probability, 0, 1, "reply_probability", 0.02)
        self.reaction_probability = _clamp(self.reaction_probability, 0, 1, "reaction_probability", 0.05)
        self.max_context_messages = max(0, self.max_context_messages)
        self.max_session_messages = max(1, self.max_session_messages)
        if not self.system_prompt:
            self.system_prompt = DEFAULT_SYSTEM_PROMPT


@dataclass
class SchedulerConfig:
    channels: list[int] = field(default_factory=list)
    min_hours: float = 12.0
    max_hours: float = 24.0


@dataclass
class Config:
    """Bot-wide configuration loaded from config.toml with env var overrides for secrets."""

    discord: DiscordConfig = field(default_factory=DiscordConfig)
    backend: BackendConfig = field(default_factory=BackendConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    behavior: BehaviorConfig = field(default_factory=BehaviorConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)

    data_dir: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "data"
    )

    @classmethod
    def from_file(cls, path: Path | None = None) -> Config:
        """Load configuration from a TOML file, merging over defaults.

        Environment variables override ``discord.token`` (``DISCORD_TOKEN``),
        ``discord.admin_ids`` (``ADMIN_USER_IDS`` or ``ADMIN_USER_ID``),
        and ``backend.api_key`` (``API_KEY``).
        """
        config_path = path or _CONFIG_PATH
        raw = _load_toml(config_path)

        # Handle legacy flat keys by mapping them into nested dicts
        raw = _migrate_legacy_keys(raw)

        config = cls()
        _merge_dataclass(config, raw)

        # Re-run validation after merge (setattr bypasses __post_init__)
        config.discord.__post_init__()
        config.backend.__post_init__()
        config.llm.__post_init__()
        config.behavior.__post_init__()

        return config

    def __post_init__(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def validate(self) -> None:
        """Validate that required fields are present. Call after from_file()."""
        if not self.discord.token:
            raise ValueError(
                "Discord token required: set discord.token in config.toml or DISCORD_TOKEN env var"
            )
        if not self.discord.admin_ids:
            raise ValueError(
                "Admin IDs required: set discord.admin_ids in config.toml or ADMIN_USER_IDS env var"
            )


def _migrate_legacy_keys(raw: dict) -> dict:
    """Map legacy TOML structure to the new nested format.

    Handles the old flat-ish layout where [backend] held api_key/model/base_url
    and [llm] held temperature/max_tokens/sample_size separately.
    """
    out = dict(raw)

    # [discord] — admin_user_id fallback
    d = out.get("discord", {})
    if "admin_user_id" in d and "admin_ids" not in d:
        val = d.pop("admin_user_id")
        if isinstance(val, int) and val:
            d["admin_ids"] = [val]

    # Apply env overrides into the discord dict
    env_token = os.environ.get("DISCORD_TOKEN")
    if env_token:
        d.setdefault("token", "")
        d["token"] = env_token
    admin_env = os.environ.get("ADMIN_USER_IDS") or os.environ.get("ADMIN_USER_ID")
    if admin_env:
        d["admin_ids"] = _parse_admin_ids(admin_env, None)
    if d:
        out["discord"] = d

    # [backend] stays as-is (active, api_key, model, base_url, enable_*)
    b = out.get("backend", {})
    env_api = os.environ.get("API_KEY")
    if env_api:
        b["api_key"] = env_api
    if b:
        out["backend"] = b

    # [llm] stays as-is (temperature, max_tokens, sample_size)

    # [behavior] stays as-is

    # [scheduler] — map legacy 'channels' key
    return out
