from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import tomli_w

log = logging.getLogger("faithful.config")

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.toml"

DEFAULT_SYSTEM_PROMPT = (
    "You are {name}. Here's how {name} talks:\n\n"
    "{examples}\n"
    "{memories}"
    "Write exactly like {name} -- same slang, same punctuation, same energy.\n"
    "If {name} types in all lowercase, you do too. If {name} is blunt, be blunt.\n"
    "Don't clean up the language, don't add politeness, don't over-explain.\n\n"
    "Keep your messages short and natural like a real Discord user.\n"
    "Use newlines to break up separate thoughts."
)

# Maps Config field names to (section, key) in the TOML file
_FIELD_TO_TOML: dict[str, tuple[str, str]] = {
    "active_backend": ("backend", "active"),
    "api_key": ("backend", "api_key"),
    "model": ("backend", "model"),
    "base_url": ("backend", "base_url"),
    "host": ("backend", "host"),
    "temperature": ("llm", "temperature"),
    "max_tokens": ("llm", "max_tokens"),
    "sample_size": ("llm", "sample_size"),
    "reply_probability": ("behavior", "reply_probability"),
    "debounce_delay": ("behavior", "debounce_delay"),
    "persona_name": ("behavior", "persona_name"),
    "max_context_messages": ("behavior", "max_context_messages"),
    "conversation_expiry": ("behavior", "conversation_expiry"),
    "enable_web_search": ("behavior", "enable_web_search"),
    "enable_memory": ("behavior", "enable_memory"),
}


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


@dataclass
class Config:
    """Bot-wide configuration loaded from config.toml with env var overrides for secrets."""

    # Discord
    discord_token: str = ""
    admin_user_id: int = 0
    admin_only_upload: bool = True

    # Backend
    active_backend: str = "markov"
    api_key: str = ""
    model: str = ""
    base_url: str = ""
    host: str = ""

    # LLM
    temperature: float = 1.0
    max_tokens: int = 1024
    sample_size: int = 300

    # Behavior
    persona_name: str = "faithful"
    reply_probability: float = 0.02
    debounce_delay: float = 3.0
    conversation_expiry: float = 300.0
    max_context_messages: int = 20
    enable_web_search: bool = False
    enable_memory: bool = False
    system_prompt: str = ""

    # Scheduler
    spontaneous_channels: list[int] = field(default_factory=list)
    scheduler_min_hours: float = 12.0
    scheduler_max_hours: float = 24.0

    # Paths
    data_dir: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "data"
    )
    _config_path: Path = field(default=_CONFIG_PATH, repr=False)

    @classmethod
    def from_file(cls, path: Path | None = None) -> Config:
        """Load configuration from a TOML file. Environment variables
        override ``discord.token`` (``DISCORD_TOKEN``), ``discord.admin_user_id``
        (``ADMIN_USER_ID``), and ``backend.api_key`` (``API_KEY``)."""
        config_path = path or _CONFIG_PATH
        raw = _load_toml(config_path)

        d = raw.get("discord", {})
        b = raw.get("backend", {})
        llm = raw.get("llm", {})
        beh = raw.get("behavior", {})
        sch = raw.get("scheduler", {})

        return cls(
            discord_token=os.environ.get("DISCORD_TOKEN", d.get("token", "")),
            admin_user_id=int(os.environ.get("ADMIN_USER_ID", d.get("admin_user_id", 0))),
            admin_only_upload=d.get("admin_only_upload", True),

            active_backend=b.get("active", "markov"),
            api_key=os.environ.get("API_KEY", b.get("api_key", "")),
            model=b.get("model", ""),
            base_url=b.get("base_url", ""),
            host=b.get("host", ""),

            temperature=float(llm.get("temperature", 1.0)),
            max_tokens=int(llm.get("max_tokens", 1024)),
            sample_size=int(llm.get("sample_size", 300)),

            persona_name=beh.get("persona_name", "faithful"),
            reply_probability=float(beh.get("reply_probability", 0.02)),
            debounce_delay=float(beh.get("debounce_delay", 3.0)),
            conversation_expiry=float(beh.get("conversation_expiry", 300.0)),
            max_context_messages=int(beh.get("max_context_messages", 20)),
            enable_web_search=beh.get("enable_web_search", False),
            enable_memory=beh.get("enable_memory", False),
            system_prompt=beh.get("system_prompt", ""),

            spontaneous_channels=sch.get("channels", []),
            scheduler_min_hours=float(sch.get("min_hours", 12)),
            scheduler_max_hours=float(sch.get("max_hours", 24)),

            data_dir=Path(__file__).resolve().parent.parent / "data",
            _config_path=config_path,
        )

    def __post_init__(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

        if not self.discord_token:
            raise ValueError(
                "Discord token required: set discord.token in config.toml or DISCORD_TOKEN env var"
            )
        if not self.admin_user_id:
            raise ValueError(
                "Admin user ID required: set discord.admin_user_id in config.toml or ADMIN_USER_ID env var"
            )

        self.debounce_delay = _clamp(self.debounce_delay, 0, 60, "debounce_delay", 3.0)
        self.reply_probability = _clamp(self.reply_probability, 0, 1, "reply_probability", 0.02)
        self.temperature = _clamp(self.temperature, 0, 2, "temperature", 1.0)
        self.sample_size = max(1, self.sample_size)
        self.max_context_messages = max(0, self.max_context_messages)
        self.max_tokens = max(1, self.max_tokens)

        if not self.system_prompt:
            self.system_prompt = DEFAULT_SYSTEM_PROMPT

    def save(self, field_name: str, value: object) -> None:
        """Update a config field in memory and persist to the TOML file."""
        current = getattr(self, field_name)
        if isinstance(current, float):
            value = float(value)  # type: ignore[arg-type]
        elif isinstance(current, int):
            value = int(value)  # type: ignore[arg-type]
        setattr(self, field_name, value)

        toml_loc = _FIELD_TO_TOML.get(field_name)
        if toml_loc is None:
            return

        section, key = toml_loc
        raw = _load_toml(self._config_path)
        raw.setdefault(section, {})[key] = value
        with open(self._config_path, "wb") as f:
            tomli_w.dump(raw, f)
