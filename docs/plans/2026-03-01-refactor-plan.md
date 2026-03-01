# Faithful Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restructure Faithful for cleaner architecture, config-file-driven settings, multi-admin support, and add reactions/custom emoji.

**Architecture:** Merge the two-level backend hierarchy into one base class, remove Markov, make config read-only, slim admin commands to corpus management, and add reaction parsing via response markers.

**Tech Stack:** Python 3.10+, discord.py, openai, anthropic, google-genai, ollama, duckduckgo-search

**No test suite exists.** Verification is via import checks (`python -c "from faithful import ..."`) and full bot startup (`python -m faithful`).

---

### Task 1: Delete Markov backend and merge base classes

**Files:**
- Delete: `faithful/backends/markov.py`
- Delete: `faithful/backends/llm.py`
- Rewrite: `faithful/backends/base.py`

**Step 1: Delete markov.py**

Delete the file `faithful/backends/markov.py`.

**Step 2: Rewrite base.py to merge Backend + BaseLLMBackend**

The new `base.py` contains `Attachment` (with `b64` property), `ToolCall` (moved from tools.py), `GenerationRequest`, and `Backend` (merged from the old `Backend` + `BaseLLMBackend`):

```python
from __future__ import annotations

import base64
import json
import logging
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from faithful.config import Config
    from faithful.memory import MemoryStore

log = logging.getLogger("faithful.backend")

SPONTANEOUS_PROMPT = (
    "Say something in the chat. Be random -- start a topic, share a thought, "
    "drop a reaction to nothing. Whatever feels in-character."
)

MAX_TOOL_ROUNDS = 5


@dataclass(frozen=True)
class Attachment:
    """A downloaded file attachment (image, etc.) from a Discord message."""

    filename: str
    content_type: str
    data: bytes

    @property
    def b64(self) -> str:
        """Base64-encoded data as a string."""
        return base64.b64encode(self.data).decode()


@dataclass
class ToolCall:
    """A tool invocation parsed from an LLM response."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GenerationRequest:
    """Everything a backend needs to produce a response."""

    prompt: str
    system_prompt: str
    context: list[dict[str, str]] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    channel_id: int = 0
    participants: dict[int, str] = field(default_factory=dict)
    guild_id: int = 0


class Backend:
    """Base class for all text-generation backends.

    Subclasses implement ``_call_api`` for basic generation.
    For tool support, subclasses also implement ``_format_tools``,
    ``_call_with_tools``, and ``_append_tool_result``.
    """

    memory_store: MemoryStore | None = None

    _has_native_search: bool = False
    """Subclasses with server-side web search set this to True."""

    def __init__(self, config: Config) -> None:
        self.config = config

    async def setup(self, examples: list[str]) -> None:
        """Called when the example corpus changes (or on first load)."""
        pass  # LLM backends don't need pre-processing

    @abstractmethod
    async def _call_api(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        attachments: list[Attachment] | None = None,
    ) -> str:
        """Send messages to the provider and return the response text."""

    @staticmethod
    def _parse_json_args(raw: str | dict | None) -> dict[str, Any]:
        """Parse JSON tool arguments with fallback."""
        if isinstance(raw, dict):
            return raw
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}

    def _get_active_tools(self) -> list[dict[str, Any]]:
        """Return provider-agnostic tool defs enabled by config."""
        from faithful.tools import TOOL_REMEMBER_CHANNEL, TOOL_REMEMBER_USER, TOOL_WEB_SEARCH

        tools: list[dict[str, Any]] = []
        if self.config.enable_web_search and not self._has_native_search:
            tools.append(TOOL_WEB_SEARCH)
        if self.config.enable_memory and self.memory_store is not None:
            tools.append(TOOL_REMEMBER_USER)
            tools.append(TOOL_REMEMBER_CHANNEL)
        return tools

    async def generate(self, request: GenerationRequest) -> str:
        messages: list[dict[str, str]] = list(request.context)

        if request.prompt:
            messages.append({"role": "user", "content": request.prompt})
        elif request.attachments:
            messages.append({"role": "user", "content": ""})
        else:
            messages.append({"role": "user", "content": SPONTANEOUS_PROMPT})

        tools = self._get_active_tools()
        if tools:
            return await self._generate_with_tools(
                request.system_prompt,
                messages,
                tools,
                request.attachments or None,
                request.channel_id,
                request.participants,
            )

        return await self._call_api(
            request.system_prompt, messages, request.attachments or None
        )

    async def _generate_with_tools(
        self,
        system_prompt: str,
        messages: list[Any],
        tools: list[dict[str, Any]],
        attachments: list[Attachment] | None,
        channel_id: int,
        participants: dict[int, str],
    ) -> str:
        from faithful.tools import ToolExecutor

        formatted_tools = self._format_tools(tools)
        executor = ToolExecutor(self.memory_store, channel_id, participants)

        for _ in range(MAX_TOOL_ROUNDS):
            text, tool_calls = await self._call_with_tools(
                system_prompt, messages, formatted_tools, attachments
            )
            attachments = None  # Only pass attachments on the first round

            if not tool_calls:
                return (text or "").strip()

            for call in tool_calls:
                result = await executor.execute(call.name, call.arguments)
                log.info("Tool %s(%s) -> %s", call.name, call.arguments, result[:200])
                messages = self._append_tool_result(messages, call, result)

        # Exhausted rounds — do a final call without tools
        return await self._call_api(system_prompt, messages)

    def _format_tools(self, tools: list[dict[str, Any]]) -> Any:
        """Convert provider-agnostic tool defs to provider format."""
        raise NotImplementedError

    async def _call_with_tools(
        self,
        system_prompt: str,
        messages: list[Any],
        tools: Any,
        attachments: list[Attachment] | None = None,
    ) -> tuple[str | None, list[ToolCall]]:
        """Call the API with tools. Return (text_response, tool_calls)."""
        raise NotImplementedError

    def _append_tool_result(
        self,
        messages: list[Any],
        call: ToolCall,
        result: str,
    ) -> list[Any]:
        """Append a tool call and its result to messages in provider format."""
        raise NotImplementedError
```

**Step 3: Delete llm.py**

Delete the file `faithful/backends/llm.py`.

**Step 4: Verify imports**

Run: `python -c "from faithful.backends.base import Backend, Attachment, ToolCall, GenerationRequest; print('OK')"`
Expected: `OK`

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor: merge Backend + BaseLLMBackend, delete Markov backend"
```

---

### Task 2: Rename backend files and update registry

**Files:**
- Rename: `faithful/backends/openai_backend.py` → `faithful/backends/openai.py`
- Rename: `faithful/backends/openai_compat_backend.py` → `faithful/backends/openai_compat.py`
- Rename: `faithful/backends/anthropic_backend.py` → `faithful/backends/anthropic.py`
- Rename: `faithful/backends/gemini_backend.py` → `faithful/backends/gemini.py`
- Rename: `faithful/backends/ollama_backend.py` → `faithful/backends/ollama.py`
- Modify: `faithful/backends/__init__.py`

**Step 1: Rename all backend files**

```bash
cd faithful/backends
git mv openai_backend.py openai.py
git mv openai_compat_backend.py openai_compat.py
git mv anthropic_backend.py anthropic.py
git mv gemini_backend.py gemini.py
git mv ollama_backend.py ollama.py
```

**Step 2: Update __init__.py**

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from .anthropic import AnthropicBackend
from .gemini import GeminiBackend
from .ollama import OllamaBackend
from .openai import OpenAIBackend
from .openai_compat import OpenAICompatibleBackend

if TYPE_CHECKING:
    from faithful.config import Config
    from .base import Backend

_BACKENDS: dict[str, type[Backend]] = {
    "ollama": OllamaBackend,
    "openai": OpenAIBackend,
    "openai-compatible": OpenAICompatibleBackend,
    "gemini": GeminiBackend,
    "anthropic": AnthropicBackend,
}

BACKEND_NAMES = list(_BACKENDS.keys())


def get_backend(name: str, config: Config) -> Backend:
    """Instantiate and return a backend by name."""
    cls = _BACKENDS.get(name.lower())
    if cls is None:
        raise ValueError(
            f"Unknown backend '{name}'. Choose from: {', '.join(_BACKENDS)}"
        )
    return cls(config)
```

**Step 3: Update imports in each backend file**

Each backend file needs its imports updated to reflect the new base module structure. Replace `from .llm import BaseLLMBackend` or `from .llm import SPONTANEOUS_PROMPT, BaseLLMBackend` with `from .base import Backend` (and `SPONTANEOUS_PROMPT` where used — only anthropic.py).

In every backend file, also replace:
- `from .base import Attachment` → already in new base
- `BaseLLMBackend` → `Backend`
- `from faithful.tools import ToolCall as TC` → `from .base import ToolCall`
- `from faithful.tools import ToolCall` (TYPE_CHECKING block) → remove, use `from .base import ToolCall`

**openai.py**: Replace `from .llm import BaseLLMBackend` with `from .base import Attachment, Backend, ToolCall`. Change `class OpenAIBackend(BaseLLMBackend)` to `class OpenAIBackend(Backend)`. Remove `from .base import Attachment`. Remove `from faithful.tools import ToolCall` TYPE_CHECKING import. Replace `from faithful.tools import ToolCall as TC` inside `_call_with_tools` with just `ToolCall` (already imported).

**openai_compat.py**: Same pattern. Replace `from .llm import BaseLLMBackend` with `from .base import Attachment, Backend, ToolCall`. Change class to extend `Backend`. Remove redundant imports.

**anthropic.py**: Replace `from .llm import SPONTANEOUS_PROMPT, BaseLLMBackend` with `from .base import Attachment, Backend, SPONTANEOUS_PROMPT, ToolCall`. Change class to extend `Backend`. Remove redundant imports.

**gemini.py**: Replace `from .llm import BaseLLMBackend` with `from .base import Attachment, Backend, ToolCall`. Change class to extend `Backend`. Remove redundant imports.

**ollama.py**: Replace `from .llm import BaseLLMBackend` with `from .base import Attachment, Backend, ToolCall`. Change class to extend `Backend`. Remove redundant imports.

**Step 4: Verify imports**

Run: `python -c "from faithful.backends import get_backend; print('OK')"`
Expected: `OK`

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor: rename backend files, update registry and imports"
```

---

### Task 3: Update backends to use new helpers

**Files:**
- Modify: `faithful/backends/openai.py`
- Modify: `faithful/backends/openai_compat.py`
- Modify: `faithful/backends/anthropic.py`
- Modify: `faithful/backends/gemini.py`
- Modify: `faithful/backends/ollama.py`
- Modify: `faithful/tools.py`

**Step 1: Remove ToolCall from tools.py**

In `faithful/tools.py`, remove the `ToolCall` dataclass (lines 17-23) and its `dataclass`/`field` imports. Update all internal references to import `ToolCall` from `faithful.backends.base` instead. The `ToolExecutor` doesn't use `ToolCall` directly (it receives name + args), so only the import line in `TYPE_CHECKING` needs removing.

**Step 2: Replace base64 encoding with att.b64 in each backend**

In every backend, find `base64.b64encode(att.data).decode()` and replace with `att.b64`. Remove `import base64` from files where it's no longer needed.

Specific locations:
- `openai.py:44` — `b64 = base64.b64encode(att.data).decode()` → `b64 = att.b64`
- `openai_compat.py:53` — same replacement
- `anthropic.py:80` — same replacement
- `gemini.py:59` and `gemini.py:110` — same replacement (two locations)
- `ollama.py:41` — `base64.b64encode(att.data).decode()` → `att.b64`

Remove `import base64` from all five backend files.

**Step 3: Replace JSON parsing with _parse_json_args in each backend**

Specific locations:
- `openai.py` in `_call_with_tools`: Replace the try/except JSON block (lines 112-115) with `args = self._parse_json_args(item.arguments)`
- `openai_compat.py` in `_call_with_tools`: Replace the try/except block (lines 116-119) with `args = self._parse_json_args(tc.function.arguments)`
- `ollama.py` in `_call_with_tools`: Replace the args parsing block (lines 105-110) with `args = self._parse_json_args(func.get("arguments"))`
- `gemini.py` in `_append_tool_result`: Replace the try/except block (lines 163-165) with `result_dict = self._parse_json_args(result)`

Remove `import json` from backend files where it's no longer used (openai.py — still needs json.dumps in _append_tool_result, so keep it; openai_compat.py — same; ollama.py — can remove; gemini.py — can remove since json.loads replaced).

**Step 4: Verify imports**

Run: `python -c "from faithful.backends import get_backend; from faithful.tools import ToolExecutor; print('OK')"`
Expected: `OK`

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor: use Attachment.b64 and _parse_json_args helpers across backends"
```

---

### Task 4: Simplify config system

**Files:**
- Rewrite: `faithful/config.py`
- Modify: `faithful/config.example.toml`

**Step 1: Rewrite config.py**

Remove `Config.save()`, `_FIELD_TO_TOML`, `tomli_w` import. Change `admin_user_id: int` to `admin_ids: list[int]`. Remove `admin_only_upload`. Add `reaction_probability`. Change default backend to `"openai-compatible"`.

```python
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

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
    """Parse admin IDs from env var (comma-separated) or TOML (int or list)."""
    if env_val:
        return [int(x.strip()) for x in env_val.split(",") if x.strip()]
    if isinstance(toml_val, list):
        return [int(x) for x in toml_val]
    if isinstance(toml_val, int) and toml_val:
        return [toml_val]
    return []


@dataclass
class Config:
    """Bot-wide configuration loaded from config.toml with env var overrides for secrets."""

    # Discord
    discord_token: str = ""
    admin_ids: list[int] = field(default_factory=list)

    # Backend
    active_backend: str = "openai-compatible"
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
    reaction_probability: float = 0.05
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

    @classmethod
    def from_file(cls, path: Path | None = None) -> Config:
        config_path = path or _CONFIG_PATH
        raw = _load_toml(config_path)

        d = raw.get("discord", {})
        b = raw.get("backend", {})
        llm = raw.get("llm", {})
        beh = raw.get("behavior", {})
        sch = raw.get("scheduler", {})

        return cls(
            discord_token=os.environ.get("DISCORD_TOKEN", d.get("token", "")),
            admin_ids=_parse_admin_ids(
                os.environ.get("ADMIN_USER_IDS"),
                d.get("admin_ids", d.get("admin_user_id", 0)),
            ),

            active_backend=b.get("active", "openai-compatible"),
            api_key=os.environ.get("API_KEY", b.get("api_key", "")),
            model=b.get("model", ""),
            base_url=b.get("base_url", ""),
            host=b.get("host", ""),

            temperature=float(llm.get("temperature", 1.0)),
            max_tokens=int(llm.get("max_tokens", 1024)),
            sample_size=int(llm.get("sample_size", 300)),

            persona_name=beh.get("persona_name", "faithful"),
            reply_probability=float(beh.get("reply_probability", 0.02)),
            reaction_probability=float(beh.get("reaction_probability", 0.05)),
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
        )

    def __post_init__(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

        if not self.discord_token:
            raise ValueError(
                "Discord token required: set discord.token in config.toml or DISCORD_TOKEN env var"
            )
        if not self.admin_ids:
            raise ValueError(
                "At least one admin ID required: set discord.admin_ids in config.toml or ADMIN_USER_IDS env var"
            )

        self.debounce_delay = _clamp(self.debounce_delay, 0, 60, "debounce_delay", 3.0)
        self.reply_probability = _clamp(self.reply_probability, 0, 1, "reply_probability", 0.02)
        self.reaction_probability = _clamp(self.reaction_probability, 0, 1, "reaction_probability", 0.05)
        self.temperature = _clamp(self.temperature, 0, 2, "temperature", 1.0)
        self.sample_size = max(1, self.sample_size)
        self.max_context_messages = max(0, self.max_context_messages)
        self.max_tokens = max(1, self.max_tokens)

        if not self.system_prompt:
            self.system_prompt = DEFAULT_SYSTEM_PROMPT
```

Note: `_parse_admin_ids` needs `from typing import Any` — add it to imports.

**Step 2: Update config.example.toml**

```toml
# Faithful Discord Bot Configuration
# Copy this file to config.toml and fill in your values.

[discord]
token = ""            # Required: your Discord bot token
admin_ids = []        # Required: list of Discord user IDs, e.g. [123456789, 987654321]

[backend]
# Options: openai, openai-compatible, ollama, gemini, anthropic
active = "openai-compatible"

# API key and model for the active LLM backend
api_key = ""
model = ""

# Optional provider-specific settings
# base_url = ""                            # Required for openai-compatible (e.g. "http://localhost:1234/v1")
# host = "http://localhost:11434"           # Ollama server address

[llm]
temperature = 1.0     # 0.0 to 2.0
max_tokens = 1024
sample_size = 300     # Example messages to include in system prompt

[behavior]
persona_name = "faithful"
reply_probability = 0.02      # 0.0 to 1.0 — chance to reply to random messages
reaction_probability = 0.05   # 0.0 to 1.0 — chance to react to messages without replying
debounce_delay = 3.0          # Seconds to wait before responding
conversation_expiry = 300.0   # Seconds before a conversation goes stale
max_context_messages = 20
enable_web_search = false     # LLM can search the web
enable_memory = false         # Per-user and per-channel memory

# Optional: custom system prompt template
# Available placeholders: {name}, {examples}, {memories}, {custom_emojis}
# system_prompt = "..."

[scheduler]
channels = []       # Channel IDs for unprompted messages
min_hours = 12
max_hours = 24
```

**Step 3: Verify**

Run: `python -c "from faithful.config import Config; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor: simplify config — multi-admin, read-only, remove tomli_w"
```

---

### Task 5: Slim down admin commands

**Files:**
- Rewrite: `faithful/cogs/admin.py`

**Step 1: Rewrite admin.py**

Remove `/set_backend`, `/set_temperature`, `/set_probability`, `/set_debounce`. Remove `can_upload()`. Update `is_admin()` to check list membership. Remove `BACKEND_NAMES` import. Remove the `bot.config.save()` calls. Keep all corpus commands, `/status`, `/generate_test`, "Add to Persona", and `/memory` group.

```python
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

    # ── Corpus Management ─────────────────────────────────

    @app_commands.command(name="upload", description="Upload a .txt file of example messages.")
    @app_commands.describe(file="A file with example messages")
    @is_admin()
    async def upload(self, interaction: discord.Interaction, file: discord.Attachment) -> None:
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

    @app_commands.command(name="add_message", description="Add a single example message.")
    @app_commands.describe(text="The example message to add")
    @is_admin()
    async def add_message(self, interaction: discord.Interaction, text: str) -> None:
        self.bot.store.add_messages([text])
        await self.bot.refresh_backend()
        await interaction.response.send_message(
            f"\u2705 Added message (total: {self.bot.store.count}).", ephemeral=True
        )

    @app_commands.command(name="list_messages", description="List stored example messages (paginated).")
    @app_commands.describe(page="Page number (20 messages per page)")
    @is_admin()
    async def list_messages(self, interaction: discord.Interaction, page: int = 1) -> None:
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

    @app_commands.command(name="remove_message", description="Remove an example message by its index number.")
    @app_commands.describe(index="1-based index of the message to remove")
    @is_admin()
    async def remove_message(self, interaction: discord.Interaction, index: int) -> None:
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

    @app_commands.command(name="clear_messages", description="Remove ALL example messages.")
    @is_admin()
    async def clear_messages(self, interaction: discord.Interaction) -> None:
        count = self.bot.store.clear_messages()
        await self.bot.refresh_backend()
        await interaction.response.send_message(
            f"\U0001f5d1\ufe0f Cleared **{count}** messages.", ephemeral=True
        )

    @app_commands.command(name="download_messages", description="Download all stored example messages as a .txt file.")
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

    @app_commands.command(name="status", description="Show current bot status and configuration.")
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
            f"**Web search:** {'on' if cfg.enable_web_search else 'off'}",
            f"**Memory:** {'on' if cfg.enable_memory else 'off'}",
            f"**Admins:** {len(cfg.admin_ids)}",
            f"**Spontaneous channels:** {len(cfg.spontaneous_channels)}",
        ]
        await interaction.response.send_message(
            "\n".join(lines), ephemeral=True
        )

    @app_commands.command(name="generate_test", description="Trigger a test response based on a prompt.")
    @app_commands.describe(prompt="The prompt to test against")
    @is_admin()
    async def generate_test(self, interaction: discord.Interaction, prompt: str) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            sampled = self.bot.store.get_sampled_messages(self.bot.config.sample_size)
            system_prompt = format_system_prompt(
                self.bot.config.system_prompt,
                self.bot.config.persona_name,
                sampled,
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
```

**Step 2: Verify**

Run: `python -c "from faithful.cogs import admin; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add -A
git commit -m "refactor: slim admin commands, multi-admin permission checks"
```

---

### Task 6: Update bot.py

**Files:**
- Modify: `faithful/bot.py`

**Step 1: Update bot.py**

Remove `swap_backend` (no longer persists — keep the method but remove the `config.save` call). Simplify `_set_backend_memory` since all backends have `memory_store`. Remove `BACKEND_NAMES` import reference (if any).

```python
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from .backends import get_backend
from .store import MessageStore

if TYPE_CHECKING:
    from .backends.base import Backend
    from .config import Config
    from .memory import MemoryStore as MemoryStoreType

log = logging.getLogger("faithful")


class Faithful(commands.Bot):
    """The persona-emulating Discord bot."""

    config: Config
    store: MessageStore
    backend: Backend
    memory_store: MemoryStoreType | None

    def __init__(self, config: Config) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            status=discord.Status.online,
            activity=discord.Game(name="being myself"),
        )

        self.config = config
        self.store = MessageStore(config)
        self.backend = get_backend(config.active_backend, config)
        self.memory_store = None

        if config.enable_memory:
            from .memory import MemoryStore
            self.memory_store = MemoryStore(config.data_dir)

        self.backend.memory_store = self.memory_store

    async def setup_hook(self) -> None:
        await self.load_extension("faithful.cogs.admin")
        await self.load_extension("faithful.cogs.chat")
        await self.load_extension("faithful.cogs.scheduler")

        examples = self.store.list_messages()
        if examples:
            await self.backend.setup(examples)
            log.info(
                "Backend '%s' initialised with %d examples.",
                self.config.active_backend,
                self.store.count,
            )
        else:
            log.warning("No example messages found. Use /upload to add some.")

    async def on_ready(self) -> None:
        log.info("Logged in as %s (ID: %s)", self.user, self.user.id)
        activity = discord.CustomActivity(name="being me")
        await self.change_presence(activity=activity)

    async def refresh_backend(self) -> None:
        """Re-setup the current backend (call after message corpus changes)."""
        examples = self.store.list_messages()
        await self.backend.setup(examples)
```

**Step 2: Verify**

Run: `python -c "from faithful.bot import Faithful; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add -A
git commit -m "refactor: simplify bot.py — remove swap_backend persistence"
```

---

### Task 7: Add reaction parsing to chunker.py

**Files:**
- Modify: `faithful/chunker.py`

**Step 1: Add extract_reactions and update chunk_response**

Add a function that parses `[react: emoji]` markers from the response text, strips them, and returns both the clean text and the list of reaction emoji.

```python
"""Message delivery — chunk text and send with typing delays."""

from __future__ import annotations

import asyncio
import re
import random

import discord

_REACTION_PATTERN = re.compile(r"\[react:\s*([^\]]+)\]")


def extract_reactions(text: str) -> tuple[str, list[str]]:
    """Strip [react: emoji] markers from text and return (clean_text, reactions)."""
    reactions = _REACTION_PATTERN.findall(text)
    clean = _REACTION_PATTERN.sub("", text).strip()
    return clean, [r.strip() for r in reactions if r.strip()]


def chunk_response(text: str) -> list[str]:
    """Split text into Discord-safe chunks (<= 2000 chars).

    Splitting priority: newlines -> sentence ends -> spaces -> hard cut.
    """
    chunks: list[str] = []

    for paragraph in text.split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        remaining = paragraph
        while remaining:
            if len(remaining) <= 2000:
                chunks.append(remaining)
                break

            # Try sentence boundary
            split_idx = -1
            for punc in (". ", "! ", "? "):
                idx = remaining.rfind(punc, 0, 1900)
                if idx > split_idx:
                    split_idx = idx + 1  # include the punctuation

            # Try space
            if split_idx <= 0:
                split_idx = remaining.rfind(" ", 0, 1900)

            # Hard cut
            if split_idx <= 0:
                split_idx = 2000

            chunks.append(remaining[:split_idx].strip())
            remaining = remaining[split_idx:].strip()

    return chunks


def typing_delay(text: str) -> float:
    """Calculate a simulated typing delay for *text* (~15 chars/sec)."""
    base = 0.8 + len(text) / 15.0
    delay = base + random.uniform(-0.3, 0.5)
    return max(1.0, min(delay, 5.0))


async def send_chunked(
    channel: discord.abc.Messageable,
    text: str,
    react_target: discord.Message | None = None,
) -> None:
    """Chunk *text*, send each piece with a typing indicator, and apply reactions."""
    clean_text, reactions = extract_reactions(text)

    for chunk in chunk_response(clean_text):
        async with channel.typing():
            await asyncio.sleep(typing_delay(chunk))
            await channel.send(chunk)

    if react_target and reactions:
        for emoji in reactions:
            try:
                await react_target.add_reaction(emoji)
            except discord.DiscordException:
                pass
```

**Step 2: Verify**

Run: `python -c "from faithful.chunker import extract_reactions; t, r = extract_reactions('hello [react: :fire:] world [react: :100:]'); print(t, r)"`
Expected: `hello  world [':fire:', ':100:']` (or similar — clean text with reactions extracted)

**Step 3: Commit**

```bash
git add -A
git commit -m "feat: add reaction parsing to chunker"
```

---

### Task 8: Add custom emoji and reactions to prompt.py

**Files:**
- Modify: `faithful/prompt.py`

**Step 1: Add get_guild_emojis helper and update format_system_prompt**

```python
"""Prompt assembly — builds a GenerationRequest from channel state."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from .backends.base import Attachment, GenerationRequest

if TYPE_CHECKING:
    from .bot import Faithful
    from .memory import MemoryStore


def get_guild_emojis(guild: discord.Guild | None) -> str:
    """Build a string listing available custom emoji for the system prompt."""
    if not guild or not guild.emojis:
        return ""
    names = [f":{e.name}:" for e in guild.emojis if e.available]
    if not names:
        return ""
    return f"Available custom emojis in this server: {', '.join(names)}\n"


def format_system_prompt(
    template: str,
    persona_name: str,
    examples: list[str],
    memories: str = "",
    custom_emojis: str = "",
) -> str:
    """Format a system prompt template with persona name, examples, memories, and emoji."""
    return template.format(
        name=persona_name,
        examples="\n".join(examples),
        memories=memories,
        custom_emojis=custom_emojis,
    )


def format_memories(
    memory_store: MemoryStore,
    channel_id: int,
    participants: dict[int, str],
) -> str:
    """Build formatted memory sections for the system prompt."""
    sections: list[str] = []

    for user_id, display_name in participants.items():
        _, facts = memory_store.get_user_memories(user_id)
        if facts:
            lines = "\n".join(f"- {f}" for f in facts)
            sections.append(f"What you know about {display_name}:\n{lines}")

    channel_mems = memory_store.get_channel_memories(channel_id)
    if channel_mems:
        lines = "\n".join(f"- {m}" for m in channel_mems)
        sections.append(f"What you know about this channel:\n{lines}")

    if not sections:
        return ""

    return "\n".join(sections) + "\n\n"


def _attachment_annotations(msg: discord.Message) -> str:
    """Return text annotations for a message's attachments."""
    parts: list[str] = []
    for att in msg.attachments:
        if att.content_type and att.content_type.startswith("image/"):
            parts.append(f"[image: {att.filename}]")
        else:
            parts.append(f"[attached: {att.filename}]")
    return " ".join(parts)


def build_context(
    history: list[discord.Message],
    bot_user: discord.User | discord.Member,
) -> list[dict[str, str]]:
    """Convert Discord message history to role/content dicts."""
    context: list[dict[str, str]] = []
    for m in history:
        content = m.content
        annotations = _attachment_annotations(m)
        if annotations:
            content = f"{content} {annotations}" if content else annotations
        if m.author == bot_user:
            context.append({"role": "assistant", "content": content})
        else:
            context.append({
                "role": "user",
                "content": f"{m.author.display_name}: {content}",
            })
    return context


def find_prompt_message(
    history: list[discord.Message],
    bot_user: discord.User | discord.Member,
) -> discord.Message | None:
    """Find the most recent non-bot message in history."""
    for msg in reversed(history):
        if msg.author != bot_user and not msg.author.bot:
            return msg
    return None


def slice_from_last_mention(
    history: list[discord.Message],
    bot_user: discord.User | discord.Member,
) -> list[discord.Message]:
    """Trim history to start from the last direct @mention of the bot."""
    start = 0
    for i, msg in enumerate(history):
        if bot_user in msg.mentions and msg.reference is None:
            start = i
    return history[start:]


async def build_request(
    channel: discord.abc.Messageable,
    bot: Faithful,
    guild: discord.Guild | None = None,
) -> tuple[GenerationRequest, discord.Message | None]:
    """Assemble a GenerationRequest from current channel state."""
    limit = bot.config.max_context_messages
    history_msgs: list[discord.Message] = []
    async for msg in channel.history(limit=limit):
        history_msgs.append(msg)
    history_msgs.reverse()

    history_msgs = slice_from_last_mention(history_msgs, bot.user)

    participants: dict[int, str] = {}
    for m in history_msgs:
        if m.author != bot.user and not m.author.bot:
            participants[m.author.id] = m.author.display_name

    prompt_msg = find_prompt_message(history_msgs, bot.user)
    prompt_content = prompt_msg.content if prompt_msg else ""

    context_msgs: list[discord.Message] = []
    if prompt_msg:
        for m in history_msgs:
            if m.id == prompt_msg.id:
                break
            context_msgs.append(m)
    else:
        context_msgs = history_msgs

    attachments: list[Attachment] = []
    if prompt_msg:
        for att in prompt_msg.attachments:
            ct = att.content_type or ""
            if ct.startswith("image/"):
                data = await att.read()
                attachments.append(Attachment(att.filename, ct, data))
            elif ct.startswith("text/"):
                data = await att.read()
                text = data.decode("utf-8", errors="replace")
                prompt_content += f"\n[File: {att.filename}]\n{text}"
            else:
                prompt_content += f"\n[Attached file: {att.filename}]"

    context = build_context(context_msgs, bot.user)
    sampled = bot.store.get_sampled_messages(bot.config.sample_size)

    memories = ""
    channel_id = 0
    if hasattr(channel, "id"):
        channel_id = channel.id  # type: ignore[union-attr]
    if bot.config.enable_memory and bot.memory_store is not None:
        memories = format_memories(bot.memory_store, channel_id, participants)

    custom_emojis = get_guild_emojis(guild)

    system_prompt = format_system_prompt(
        bot.config.system_prompt, bot.config.persona_name, sampled, memories, custom_emojis
    )

    guild_id = guild.id if guild else 0
    request = GenerationRequest(
        prompt=prompt_content,
        system_prompt=system_prompt,
        context=context,
        attachments=attachments,
        channel_id=channel_id,
        participants=participants,
        guild_id=guild_id,
    )
    return request, prompt_msg
```

**Step 2: Verify**

Run: `python -c "from faithful.prompt import format_system_prompt, get_guild_emojis; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add -A
git commit -m "feat: add custom emoji injection and guild context to prompt assembly"
```

---

### Task 9: Update chat.py with reactions

**Files:**
- Modify: `faithful/cogs/chat.py`

**Step 1: Rewrite chat.py**

Add reaction-without-replying logic. Pass `guild` to `build_request`. Pass `react_target` to `send_chunked`. Add `_maybe_react` method.

```python
"""Chat cog — handles message responses, random replies, and reactions."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING

import discord
from discord.ext import commands
from discord.utils import utcnow

from faithful.backends.base import GenerationRequest
from faithful.chunker import send_chunked
from faithful.prompt import build_request, format_system_prompt, get_guild_emojis

if TYPE_CHECKING:
    from faithful.bot import Faithful

log = logging.getLogger("faithful.chat")

_REACTION_PROMPT = (
    "React to this message with a single emoji that fits your personality. "
    "Just reply with the emoji and nothing else. If nothing fits, reply PASS.\n\n"
    "Message: {message}"
)


class Chat(commands.Cog):
    """Listens to messages and responds in-character."""

    def __init__(self, bot: Faithful) -> None:
        self.bot = bot
        self._pending: dict[int, asyncio.Task] = {}

    def _should_reply_randomly(self) -> bool:
        return random.random() < self.bot.config.reply_probability

    def _should_react(self) -> bool:
        return random.random() < self.bot.config.reaction_probability

    def _is_mentioned(self, message: discord.Message) -> bool:
        if self.bot.user is None:
            return False
        if self.bot.user.mentioned_in(message):
            return True
        if message.reference and message.reference.resolved:
            ref = message.reference.resolved
            if isinstance(ref, discord.Message) and ref.author == self.bot.user:
                age = (utcnow() - ref.created_at).total_seconds()
                return age < self.bot.config.conversation_expiry
        return False

    async def _maybe_react(self, message: discord.Message) -> None:
        """Possibly react to a message without replying."""
        if not self._should_react():
            return
        if self.bot.store.count == 0:
            return

        try:
            sampled = self.bot.store.get_sampled_messages(
                min(self.bot.config.sample_size, 50)
            )
            custom_emojis = get_guild_emojis(message.guild)
            system_prompt = format_system_prompt(
                self.bot.config.system_prompt,
                self.bot.config.persona_name,
                sampled,
                custom_emojis=custom_emojis,
            )
            request = GenerationRequest(
                prompt=_REACTION_PROMPT.format(message=message.content[:500]),
                system_prompt=system_prompt,
            )
            response = await self.bot.backend.generate(request)
            response = response.strip()

            if response and response.upper() != "PASS":
                emoji = response.split()[0]  # Take just the first token
                await message.add_reaction(emoji)
        except (discord.DiscordException, Exception):
            pass  # Reactions are best-effort

    async def _debounced_respond(
        self, channel: discord.abc.Messageable, channel_id: int,
        guild: discord.Guild | None,
    ) -> None:
        try:
            async with channel.typing():
                await asyncio.sleep(self.bot.config.debounce_delay)

            request, prompt_msg = await build_request(channel, self.bot, guild)
            response = await self.bot.backend.generate(request)

            if response:
                await send_chunked(channel, response, react_target=prompt_msg)
            elif prompt_msg:
                try:
                    await prompt_msg.add_reaction("\u26a0\ufe0f")
                except discord.DiscordException:
                    pass

        except asyncio.CancelledError:
            return
        except Exception:
            log.exception("Failed to generate response")
        finally:
            self._pending.pop(channel_id, None)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.bot.user or message.author.bot:
            return

        if self.bot.store.count == 0:
            return

        is_dm = message.guild is None
        is_mentioned = self._is_mentioned(message)

        in_conversation = False
        if not (is_mentioned or is_dm):
            history: list[discord.Message] = []
            async for m in message.channel.history(limit=7):
                history.append(m)

            if len(history) >= 2:
                for prev_msg in history[1:]:
                    if prev_msg.author == self.bot.user:
                        age = (utcnow() - prev_msg.created_at).total_seconds()
                        if age < self.bot.config.conversation_expiry:
                            in_conversation = True
                        break

        should_reply = is_dm or is_mentioned or in_conversation or self._should_reply_randomly()

        if not should_reply:
            # Even when not replying, maybe react
            asyncio.create_task(self._maybe_react(message))
            return

        channel_id = message.channel.id
        existing = self._pending.get(channel_id)
        if existing and not existing.done():
            existing.cancel()

        task = asyncio.create_task(
            self._debounced_respond(message.channel, channel_id, message.guild)
        )
        self._pending[channel_id] = task


async def setup(bot: Faithful) -> None:
    await bot.add_cog(Chat(bot))
```

**Step 2: Verify**

Run: `python -c "from faithful.cogs.chat import Chat; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add -A
git commit -m "feat: add emoji reactions and custom emoji support to chat"
```

---

### Task 10: Update scheduler.py

**Files:**
- Modify: `faithful/cogs/scheduler.py`

**Step 1: Update scheduler to pass guild and custom_emojis**

The scheduler needs to pass `custom_emojis` to `format_system_prompt`. Since it picks a random channel, it can get the guild from that channel.

```python
"""Scheduler cog — sends unprompted messages at random intervals."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import TYPE_CHECKING

from discord.ext import commands

from faithful.backends.base import GenerationRequest
from faithful.chunker import send_chunked
from faithful.prompt import format_memories, format_system_prompt, get_guild_emojis

if TYPE_CHECKING:
    from faithful.bot import Faithful

log = logging.getLogger("faithful.scheduler")


class Scheduler(commands.Cog):
    """Sends unprompted messages to configured channels."""

    def __init__(self, bot: Faithful) -> None:
        self.bot = bot
        self._task: asyncio.Task | None = None
        self._state_file = self.bot.config.data_dir / "scheduler_state.json"

    def _load_next_run(self) -> float | None:
        if not self._state_file.exists():
            return None
        try:
            with open(self._state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("next_run")
        except Exception:
            return None

    def _save_next_run(self, timestamp: float) -> None:
        try:
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump({"next_run": timestamp}, f)
        except Exception:
            log.warning("Failed to save scheduler state.")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())
            log.info("Spontaneous message scheduler started.")

    def cog_unload(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _loop(self) -> None:
        await self.bot.wait_until_ready()

        min_sec = self.bot.config.scheduler_min_hours * 3600
        max_sec = self.bot.config.scheduler_max_hours * 3600

        while True:
            try:
                next_run = self._load_next_run()
                now = time.time()

                if next_run and next_run > now:
                    delay = next_run - now
                    log.info("Next spontaneous message in %.1f hours.", delay / 3600)
                else:
                    delay = random.uniform(min_sec, max_sec)
                    self._save_next_run(now + delay)
                    log.info(
                        "Scheduled spontaneous message in %.1f hours.", delay / 3600
                    )

                await asyncio.sleep(delay)
                self._save_next_run(0)

                await self._send_spontaneous()

            except asyncio.CancelledError:
                return
            except Exception:
                log.exception("Scheduler error — retrying in 1 hour.")
                await asyncio.sleep(3600)

    async def _send_spontaneous(self) -> None:
        channels = self.bot.config.spontaneous_channels
        if not channels:
            return

        if self.bot.store.count == 0:
            return

        channel_id = random.choice(channels)
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            log.warning("Spontaneous channel %d not found.", channel_id)
            return

        cfg = self.bot.config
        sampled = self.bot.store.get_sampled_messages(cfg.sample_size)

        memories = ""
        if cfg.enable_memory and self.bot.memory_store is not None:
            memories = format_memories(self.bot.memory_store, channel_id, {})

        guild = getattr(channel, "guild", None)
        custom_emojis = get_guild_emojis(guild)

        system_prompt = format_system_prompt(
            cfg.system_prompt, cfg.persona_name, sampled, memories, custom_emojis
        )

        request = GenerationRequest(
            prompt="",
            system_prompt=system_prompt,
            channel_id=channel_id,
            guild_id=guild.id if guild else 0,
        )

        try:
            response = await self.bot.backend.generate(request)
            if response:
                await send_chunked(channel, response)  # type: ignore[arg-type]
                log.info("Sent spontaneous message to #%s.", channel)
        except Exception:
            log.exception("Failed to send spontaneous message")


async def setup(bot: Faithful) -> None:
    await bot.add_cog(Scheduler(bot))
```

**Step 2: Verify**

Run: `python -c "from faithful.cogs.scheduler import Scheduler; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add -A
git commit -m "refactor: update scheduler with guild emoji support"
```

---

### Task 11: Update pyproject.toml and CLAUDE.md

**Files:**
- Modify: `pyproject.toml`
- Modify: `CLAUDE.md`

**Step 1: Update pyproject.toml**

Remove `markovify` and `tomli-w` from dependencies:

```toml
[project]
name = "faithful"
version = "3.0.0"
description = "A Discord chatbot that emulates the tone and typing style of provided example messages."
requires-python = ">=3.10"
dependencies = [
    "discord.py>=2.3",
    "openai>=1.68",
    "ollama>=0.4",
    "google-genai>=1.0",
    "anthropic>=0.40",
    "tomli>=2.0; python_version < '3.11'",
    "duckduckgo-search>=7.0",
]

[project.scripts]
faithful = "faithful.__main__:main"

[tool.setuptools.packages.find]
include = ["faithful*"]
```

**Step 2: Update CLAUDE.md**

Update to reflect the new architecture: merged backend hierarchy, multi-admin, no Config.save(), reaction system, custom emoji, removed Markov. Update all file references and descriptions.

**Step 3: Verify full import chain**

Run: `python -c "from faithful.__main__ import main; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add -A
git commit -m "chore: update pyproject.toml and CLAUDE.md for v3.0"
```
