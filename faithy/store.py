"""Message store — CRUD for the example-message corpus."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from faithy.config import Config


class MessageStore:
    """Persist example messages in a local JSON file."""

    def __init__(self, config: "Config") -> None:
        self._path: Path = config.data_dir / "messages.json"
        self._messages: list[str] = self._load()

    # ── persistence ──────────────────────────────────────

    def _load(self) -> list[str]:
        if self._path.exists():
            with open(self._path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._messages, f, ensure_ascii=False, indent=2)

    # ── public API ───────────────────────────────────────

    def add_messages(self, lines: list[str]) -> int:
        """Add multiple messages. Returns the number added."""
        cleaned = [ln.strip() for ln in lines if ln.strip()]
        self._messages.extend(cleaned)
        self._save()
        return len(cleaned)

    def remove_message(self, index: int) -> str:
        """Remove a message by 1-based index. Returns the removed text."""
        removed = self._messages.pop(index - 1)
        self._save()
        return removed

    def clear_messages(self) -> int:
        """Remove all messages. Returns the count removed."""
        count = len(self._messages)
        self._messages.clear()
        self._save()
        return count

    def list_messages(self) -> list[str]:
        """Return a copy of all messages."""
        return list(self._messages)

    def get_all_text(self) -> str:
        """Return the full corpus as a single newline-delimited string."""
        return "\n".join(self._messages)

    @property
    def count(self) -> int:
        return len(self._messages)
